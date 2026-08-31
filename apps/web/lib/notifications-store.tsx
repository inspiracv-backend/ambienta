'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Notification, NotificationPreferences } from '@ambienta/shared';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';
import { api, mensajeDeError } from '@/lib/api-client';

interface NotificationsContextValue {
  notifications: Notification[];
  preferences: NotificationPreferences[];
  loading: boolean;
  /**
   * Por que la lista esta vacia, si es que fallo (#208).
   *
   * `null` = se pregunto y esto es lo que hay. Un texto = **no se pudo
   * preguntar**, y la pantalla tiene que decirlo: sin esto un fallo de red se
   * ve igual que "esta empresa no tiene ninguno".
   */
  errorDeCarga: string | null;
  markAllAsRead: (userId: string) => void;
  updatePreferences: (userId: string, updates: Partial<Omit<NotificationPreferences, 'userId'>>) => void;
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [preferences, setPreferences] = useState<NotificationPreferences[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const { user } = useSession();
  const { mostrarToast } = useToast();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    api
      .get<Record<string, unknown>[]>('/notifications/', { tenantId: user.tenantId })
      .then((data) => {
        if (cancelled) return;
        const mapped: Notification[] = data.map((raw) => ({
          id: String(raw.id),
          userId: String(raw.recipient_user_id ?? ''),
          tenantId: String(raw.tenant_id ?? ''),
          // La tabla `notifications` de la API no modela urgencia: tiene
          // `channel` (email / in_app), que es otra cosa. Hasta que exista un
          // campo real se asume media, en vez de inventar una prioridad que el
          // backend nunca envio.
          urgencia: 'media',
          titulo: String(raw.subject ?? ''),
          mensaje: String(raw.body ?? ''),
          fecha: String(raw.created_at ?? new Date().toISOString()),
          leida: raw.read_at !== null,
        }));
        // **Se escribe siempre, incluso vacio.** El `if (length > 0)` de antes
        // no distinguia dos cosas muy distintas:
        //
        // - la API fallo  -> quedarse con lo que hay es un respaldo razonable
        // - la API respondio **cero** -> quedarse con los datos de ejemplo es
        //   mentir, y aca la mentira mueve la campana: una empresa sin
        //   notificaciones veia tres inventadas y un contador de no leidas que
        //   no correspondia a nada.
        //
        // Un badge rojo con un numero falso hace que alguien deje lo que esta
        // haciendo para ir a mirar. Cuando descubre que no habia nada, deja de
        // creerle al badge — y entonces el aviso real pasa de largo.
        setNotifications(mapped);
      })
      // El fallo NO borra lo que ya estaba: sin red, seguir viendo lo ultimo
      // conocido es mejor que una pantalla vacia que parece un sistema roto.
      .catch((e: unknown) => {
        // **Se dice que fallo.** Con la lista vacia y sin mensaje, la
        // pantalla afirma 'no hay nada' cuando la verdad es 'no se pudo
        // preguntar' — que es la misma mentira de #208 en su otra forma.
        setErrorDeCarga(mensajeDeError(e));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user?.tenantId]);

  function markAllAsRead(userId: string) {
    // Las que de verdad cambian de estado. Marcar las ya leídas movería su
    // `read_at` a hoy y borraría cuándo se leyó en realidad.
    const pendientes = notifications.filter((n) => n.userId === userId && !n.leida);

    setNotifications((prev) => prev.map((n) => (n.userId === userId ? { ...n, leida: true } : n)));

    if (!user?.tenantId || pendientes.length === 0) return;

    const leidaEn = new Date().toISOString();

    // Una por una: la API no tiene un endpoint de marcado masivo. Con volúmenes
    // reales conviene uno; para la bandeja de una persona son pocas.
    Promise.allSettled(
      pendientes.map((n) =>
        api.patch(`/notifications/${n.id}`, { read_at: leidaEn }, { tenantId: user.tenantId }),
      ),
    ).then((resultados) => {
      const fallidas = resultados.filter((r) => r.status === 'rejected');
      if (fallidas.length === 0) return;

      // Se revierten solo las que fallaron, no la acción entera: si de diez se
      // guardaron ocho, decir que no se guardó ninguna sería falso.
      const idsFallidos = new Set(
        pendientes.filter((_, i) => resultados[i].status === 'rejected').map((n) => n.id),
      );
      setNotifications((prev) =>
        prev.map((n) => (idsFallidos.has(n.id) ? { ...n, leida: false } : n)),
      );
      mostrarToast({
        tipo: 'error',
        mensaje:
          fallidas.length === pendientes.length
            ? 'No se pudieron marcar como leídas'
            : `Quedaron ${fallidas.length} sin marcar`,
        descripcion: mensajeDeError((fallidas[0] as PromiseRejectedResult).reason),
      });
    });
  }

  /**
   * **Esto no llega a la base: no hay dónde guardarlo.**
   *
   * La API expone `/notifications/rules` y `/notifications/templates`, que son
   * configuración de la empresa, no preferencias de una persona. No existe
   * tabla ni endpoint para "este usuario quiere aviso por correo con 30, 15 y 7
   * días de anticipación".
   *
   * Se guarda en memoria y se pierde al recargar. Conectarlo necesita modelo
   * nuevo, así que va por su propio cambio, no por un parche acá.
   */
  function updatePreferences(userId: string, updates: Partial<Omit<NotificationPreferences, 'userId'>>) {
    setPreferences((prev) => {
      const existing = prev.find((p) => p.userId === userId);
      if (!existing) {
        return [...prev, { userId, canalEmail: true, canalInApp: true, anticipacionDias: [30, 15, 7], ...updates }];
      }
      return prev.map((p) => (p.userId === userId ? { ...p, ...updates } : p));
    });
  }

  return (
    <NotificationsContext.Provider value={{ notifications, preferences, loading, errorDeCarga, markAllAsRead, updatePreferences }}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error('useNotifications debe usarse dentro de <NotificationsProvider>');
  return ctx;
}
