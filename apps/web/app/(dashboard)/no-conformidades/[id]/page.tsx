'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { HistorialTimeline, NonConformityDetailView } from '@/components/organisms';
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

      {/* RF-32 y RNF-08: el tratamiento de una no conformidad es lo que se
          revisa en una auditoria — cuando se detecto, quien analizo la causa y
          quien la cerro. Tenerlo solo en el historial global obliga a filtrar
          para reconstruir el caso. */}
      <HistorialTimeline
        entidadTipo="no_conformidad"
        entidadId={nc.id}
        titulo="Historial del hallazgo"
        descripcionVacio="Cada cambio de estado, analisis de causa y el cierre quedaran aqui con su autor y fecha."
      />
    </div>
  );
}
