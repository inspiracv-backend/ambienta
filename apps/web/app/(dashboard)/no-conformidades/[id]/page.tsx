'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { NonConformityDetailView } from '@/components/organisms';
import { useAudits } from '@/lib/audits-store';
import { mockTenants } from '@/mocks/tenants';
import { mockUsers } from '@/mocks/users';

export default function NonConformityDetailPage({ params }: { params: { id: string } }) {
  const { nonConformities } = useAudits();
  const nc = nonConformities.find((n) => n.id === params.id);

  if (!nc) return notFound();

  const plant = mockTenants.flatMap((t) => t.plants).find((p) => p.id === nc.plantId);
  const responsableOptions = mockUsers.filter((u) => u.tenantId === nc.tenantId).map((u) => ({ id: u.id, nombre: u.nombre }));

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'No Conformidades', href: '/no-conformidades' }, { label: nc.hallazgo }]} />
      <NonConformityDetailView nonConformity={nc} plant={plant} responsableOptions={responsableOptions} />
    </div>
  );
}
