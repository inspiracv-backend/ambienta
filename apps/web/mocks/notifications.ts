import type { Notification, NotificationPreferences } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/** Notificaciones proactivas (RF-30 a RF-33) — mezcla de leídas/no leídas y urgencias. */
export const mockNotifications: Notification[] = [
  {
    id: 'notif-1',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    userId: 'user-admin-empresa',
    urgencia: 'alta',
    titulo: 'DAE 2026 vencida',
    mensaje: 'La declaración DAE 2026 de Planta Talca está vencida. Regulariza a la brevedad.',
    leida: false,
    fecha: addDays(-1),
    obligationId: 'obl-3',
  },
  {
    id: 'notif-2',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    userId: 'user-admin-empresa',
    urgencia: 'media',
    titulo: 'SIDREP Q3 2026 por vencer',
    mensaje: 'Quedan pocos días para presentar la declaración SIDREP Q3 2026 de Planta Rancagua.',
    leida: false,
    fecha: addDays(-2),
    obligationId: 'obl-1',
  },
  {
    id: 'notif-3',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    userId: 'user-admin-empresa',
    urgencia: 'baja',
    titulo: 'RCA Planta Rancagua actualizada',
    mensaje: 'Se actualizó el artículo del considerando 12 de la RCA N° 145/2019.',
    leida: true,
    fecha: addDays(-10),
  },
];

export const mockNotificationPreferences: NotificationPreferences[] = [
  {
    userId: 'user-admin-empresa',
    canalEmail: true,
    canalInApp: true,
    anticipacionDias: [30, 15, 7],
  },
];
