'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { SubTenantsListTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useGestores } from '@/lib/gestores-store';
import { useTenants } from '@/lib/tenants-store';

/** S-27 Listado de Clientes (Sub-tenants) del Gestor. */
export default function GestoresPage() {
  const router = useRouter();
  const { user } = useSession();
  const { tenants } = useTenants();
  const { subTenants } = useGestores();

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
  const visibleSubTenants = subTenants.filter((s) => s.gestorTenantId === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Gestores — Clientes</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>
      <SubTenantsListTable subTenants={visibleSubTenants} />
    </div>
  );
}
