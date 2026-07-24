'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { AuditsListTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useAudits } from '@/lib/audits-store';
import { mockTenants } from '@/mocks/tenants';

/** S-20 Listado de Auditorías. */
export default function AuditoriasPage() {
  const router = useRouter();
  const { user } = useSession();
  const { audits } = useAudits();

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

  const visibleAudits = audits.filter(
    (a) => a.tenantId === user.tenantId && scopedPlants.some((p) => p.id === a.plantId),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Auditorías</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>
      <AuditsListTable audits={visibleAudits} plants={scopedPlants} />
    </div>
  );
}
