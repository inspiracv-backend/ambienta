'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { ObligationsListTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useObligations } from '@/lib/obligations-store';
import { mockTenants } from '@/mocks/tenants';

/**
 * S-13 Listado de Obligaciones. Fetching real: reemplazar por
 * GET /tenants/:id/obligations cuando exista spec aprobada (RF-14/RF-15).
 */
export default function ObligacionesPage() {
  const router = useRouter();
  const { user } = useSession();
  const { obligations } = useObligations();

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

  const tenant = mockTenants.find((t) => t.id === user.tenantId);
  const isVistaSimplificada = user.role === 'admin_empresa';
  const scopedPlants =
    !isVistaSimplificada && user.plantIds.length > 0
      ? (tenant?.plants ?? []).filter((p) => user.plantIds.includes(p.id))
      : tenant?.plants ?? [];

  const visibleObligations = obligations.filter(
    (o) => o.tenantId === user.tenantId && scopedPlants.some((p) => p.id === o.plantId),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Obligaciones y Declaraciones</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>
      <ObligationsListTable obligations={visibleObligations} plants={scopedPlants} />
    </div>
  );
}
