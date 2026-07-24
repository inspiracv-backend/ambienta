'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { AuditDetailView } from '@/components/organisms';
import { useAudits } from '@/lib/audits-store';
import { mockTenants } from '@/mocks/tenants';
import { mockLegalNorms } from '@/mocks/catalog';

export default function AuditDetailPage({ params }: { params: { id: string } }) {
  const { audits, nonConformities } = useAudits();
  const audit = audits.find((a) => a.id === params.id);

  if (!audit) return notFound();

  const plant = mockTenants.flatMap((t) => t.plants).find((p) => p.id === audit.plantId);
  const normativas = mockLegalNorms.filter((n) => audit.normativaIds.includes(n.id));
  const hallazgos = nonConformities.filter((nc) => nc.auditId === audit.id);

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Auditorías', href: '/auditorias' }, { label: plant?.nombre ?? audit.plantId }]} />
      <AuditDetailView audit={audit} plant={plant} normativas={normativas} hallazgos={hallazgos} />
    </div>
  );
}
