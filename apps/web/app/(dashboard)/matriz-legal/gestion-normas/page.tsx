'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { TenantNormsManager } from '@/components/organisms';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';

export default function GestionNormasPage() {
  const router = useRouter();
  const { user } = useSession();
  const { tenants } = useTenants();

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

  const tenant = tenants.find((t) => t.id === user.tenantId);

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Matriz Legal', href: '/matriz-legal' }, { label: 'Gestionar RCAs / ISO' }]} />
      <h1 className="text-2xl font-semibold text-slate-900">Gestión de RCAs e ISO</h1>
      {tenant && <TenantNormsManager tenantId={tenant.id} plantIds={tenant.plants.map((p) => p.id)} />}
    </div>
  );
}
