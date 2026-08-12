'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Notification, NotificationPreferences } from '@ambienta/shared';
import { mockNotifications, mockNotificationPreferences } from '@/mocks/notifications';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';
import { api, mensajeDeError } from '@/lib/api-client';

interface NotificationsContextValue {
  notifications: Notification[];
  preferences: NotificationPreferences[];
  loading: boolean;
  markAllAsRead: (userId: string) => void;
  updatePreferences: (userId: string, updates: Partial<Omit<NotificationPreferences, 'userId'>>) => void;
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>(mockNotifications);
  const [preferences, setPreferences] = useState<NotificationPreferences[]>(mockNotificationPreferences);
  const [loading, setLoading] = useState(true);
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
        if (mapped.length > 0) setNotifications(mapped);
      })
      .catch(() => {})
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
    <NotificationsContext.Provider value={{ notifications, preferences, loading, markAllAsRead, updatePreferences }}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error('useNotifications debe usarse dentro de <NotificationsProvider>');
  return ctx;
}
