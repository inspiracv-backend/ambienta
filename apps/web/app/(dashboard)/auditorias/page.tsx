'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { AuditsListTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useAudits } from '@/lib/audits-store';
import { useTenants } from '@/lib/tenants-store';

/** S-20 Listado de Auditorías. */
export default function AuditoriasPage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const { audits, errorDeCarga } = useAudits();

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

  const visibleAudits = audits.filter(
    (a) => a.tenantId === user.tenantId && scopedPlants.some((p) => p.id === a.plantId),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Auditorías</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>
      {errorDeCarga && (
        <p
          role="alert"
          className="rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          No se pudieron cargar las auditorías: {errorDeCarga}. Lo que se ve está
          vacío porque no se pudo preguntar, no porque no haya nada.
        </p>
      )}
      <AuditsListTable audits={visibleAudits} plants={scopedPlants} />
    </div>
  );
}
