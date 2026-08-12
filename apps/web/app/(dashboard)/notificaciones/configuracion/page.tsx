'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { NotificationPreferencesForm } from '@/components/organisms';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { useNotifications } from '@/lib/notifications-store';

/** S-32 Configuración de Notificaciones. */
export default function ConfiguracionNotificacionesPage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { preferences } = useNotifications();

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

  const userPreferences = preferences.find((p) => p.userId === user.id) ?? {
    userId: user.id,
    canalEmail: true,
    canalInApp: true,
    anticipacionDias: [30, 15, 7],
  };

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Notificaciones', href: '/notificaciones' }, { label: 'Configuración' }]} />
      <h1 className="text-2xl font-semibold text-slate-900">Configuración de notificaciones</h1>
      <NotificationPreferencesForm preferences={userPreferences} />
    </div>
  );
}
