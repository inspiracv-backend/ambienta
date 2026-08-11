'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { NonConformitiesListTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useAudits } from '@/lib/audits-store';
import { useTenants } from '@/lib/tenants-store';

/** S-22 Listado de No Conformidades. */
export default function NoConformidadesPage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const { nonConformities } = useAudits();

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

  const tenant = tenants.find((t) => t.id === user.tenantId);
  const isVistaSimplificada = user.role === 'admin_empresa';
  const scopedPlants =
    !isVistaSimplificada && user.plantIds.length > 0
      ? (tenant?.plants ?? []).filter((p) => user.plantIds.includes(p.id))
      : tenant?.plants ?? [];

  const visibleNCs = nonConformities.filter(
    (nc) => nc.tenantId === user.tenantId && scopedPlants.some((p) => p.id === nc.plantId),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">No Conformidades</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>
      <NonConformitiesListTable nonConformities={visibleNCs} plants={scopedPlants} />
    </div>
  );
}
