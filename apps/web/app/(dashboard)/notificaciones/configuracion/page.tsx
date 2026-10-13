'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { NotificationPreferencesForm } from '@/components/organisms';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';

/** S-32 Configuración de Notificaciones. */
export default function ConfiguracionNotificacionesPage() {
  const router = useRouter();
  const { user, cargando } = useSession();

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

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Notificaciones', href: '/notificaciones' }, { label: 'Configuración' }]} />
      <h1 className="text-2xl font-semibold text-slate-900">Configuración de notificaciones</h1>
      {user.tenantId ? (
        <NotificationPreferencesForm tenantId={user.tenantId} />
      ) : (
        <p className="text-sm text-slate-500">Los avisos se configuran por empresa, y esta sesión no tiene una.</p>
      )}
    </div>
  );
}
