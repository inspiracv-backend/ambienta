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
  const { user, cargando } = useSession();
  const { notifications, markAllAsRead, errorDeCarga } = useNotifications();

  useEffect(() => {
    if (!cargando && user === null) router.replace('/login');
  }, [cargando, user, router]);

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
      {errorDeCarga && (
        <p
          role="alert"
          className="rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          No se pudieron cargar las notificaciones: {errorDeCarga}. Lo que se ve está
          vacío porque no se pudo preguntar, no porque no haya nada.
        </p>
      )}

      <NotificationCenter notifications={visibleNotifications} onMarkAllAsRead={() => markAllAsRead(user.id)} />
    </div>
  );
}
