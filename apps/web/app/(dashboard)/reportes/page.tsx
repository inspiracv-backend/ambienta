'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { ReportGenerator, AuditFolderExport, ReporteCumplimientoPdf } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useObligations } from '@/lib/obligations-store';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { useAudits } from '@/lib/audits-store';
import { useTenants } from '@/lib/tenants-store';

/** S-39 Reportes + S-40 Exportación de Carpeta de Auditoría (RF-50). */
export default function ReportesPage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { obligations } = useObligations();
  const { norms } = useLegalMatrix();
  const { audits, nonConformities } = useAudits();
  const { tenants } = useTenants();

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

  // Del store en vivo: si se carga el logo en Perfil Empresa, el informe
  // impreso debe reflejarlo sin recargar.
  const tenant = tenants.find((t) => t.id === user.tenantId);
  const isVistaSimplificada = user.role === 'admin_empresa';
  const scopedPlants =
    !isVistaSimplificada && user.plantIds.length > 0
      ? (tenant?.plants ?? []).filter((p) => user.plantIds.includes(p.id))
      : (tenant?.plants ?? []);

  const scopedObligations = obligations.filter(
    (o) => o.tenantId === user.tenantId && scopedPlants.some((p) => p.id === o.plantId),
  );
  const scopedNorms = norms.filter(
    (n) => (n.tenantId === null || n.tenantId === user.tenantId) && n.plantIds.some((id) => scopedPlants.some((p) => p.id === id)),
  );
  const scopedAudits = audits.filter((a) => a.tenantId === user.tenantId && scopedPlants.some((p) => p.id === a.plantId));
  const scopedNcs = nonConformities.filter(
    (nc) => nc.tenantId === user.tenantId && scopedPlants.some((p) => p.id === nc.plantId),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Reportes</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>

      <ReportGenerator
        plants={scopedPlants}
        obligations={scopedObligations}
        norms={scopedNorms}
        nonConformities={scopedNcs}
        tenant={tenant}
        usuario={user}
      />

      {tenant && (
        <ReporteCumplimientoPdf
          tenant={tenant}
          usuario={user}
          plants={scopedPlants}
          obligations={scopedObligations}
          norms={scopedNorms}
          nonConformities={scopedNcs}
        />
      )}

      {scopedAudits.length > 0 && (
        <AuditFolderExport audits={scopedAudits} plants={scopedPlants} nonConformities={scopedNcs} />
      )}
    </div>
  );
}
