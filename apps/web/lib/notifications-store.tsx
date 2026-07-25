'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Notification, NotificationPreferences } from '@ambienta/shared';
import { mockNotifications, mockNotificationPreferences } from '@/mocks/notifications';

interface NotificationsContextValue {
  notifications: Notification[];
  preferences: NotificationPreferences[];
  markAllAsRead: (userId: string) => void;
  updatePreferences: (userId: string, updates: Partial<Omit<NotificationPreferences, 'userId'>>) => void;
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

/** Estado en memoria para esta iteración (mismo patrón que los demás stores). */
export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>(mockNotifications);
  const [preferences, setPreferences] = useState<NotificationPreferences[]>(mockNotificationPreferences);

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
    <NotificationsContext.Provider value={{ notifications, preferences, markAllAsRead, updatePreferences }}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error('useNotifications debe usarse dentro de <NotificationsProvider>');
  return ctx;
}
