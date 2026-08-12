'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Notification, NotificationPreferences } from '@ambienta/shared';
import { mockNotifications, mockNotificationPreferences } from '@/mocks/notifications';
import { useSession } from '@/lib/session';
import { api } from '@/lib/api-client';

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
    setNotifications((prev) => prev.map((n) => (n.userId === userId ? { ...n, leida: true } : n)));
  }

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
