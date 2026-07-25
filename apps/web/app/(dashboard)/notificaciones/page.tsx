'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { FileSpreadsheet, Settings2 } from 'lucide-react';
import { Spinner } from '@/components/atoms';
import { NotificationCenter } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useNotifications } from '@/lib/notifications-store';

/** S-31 Centro de Notificaciones. */
export default function NotificacionesPage() {
  const router = useRouter();
  const { user } = useSession();
  const { notifications, markAllAsRead } = useNotifications();

  useEffect(() => {
    if (user === null && !window.localStorage.getItem('ambienta.mockUserId')) router.replace('/login');
  }, [user, router]);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const visibleNotifications = notifications.filter((n) => n.userId === user.id);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-slate-900">Notificaciones</h1>
        <div className="flex gap-2">
          <Link
            href="/notificaciones/templates"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <FileSpreadsheet className="h-4 w-4" aria-hidden />
            Templates Excel
          </Link>
          <Link
            href="/notificaciones/configuracion"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Settings2 className="h-4 w-4" aria-hidden />
            Configuración
          </Link>
        </div>
      </div>

      <NotificationCenter notifications={visibleNotifications} onMarkAllAsRead={() => markAllAsRead(user.id)} />
    </div>
  );
}
