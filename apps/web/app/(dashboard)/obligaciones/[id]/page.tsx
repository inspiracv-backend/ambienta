'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { HistorialTimeline, ObligationDetailView } from '@/components/organisms';
import { useObligations } from '@/lib/obligations-store';
import { mockUsers } from '@/mocks/users';

export default function ObligationDetailPage({ params }: { params: { id: string } }) {
  const { obligations } = useObligations();
  const obligation = obligations.find((o) => o.id === params.id);

  if (!obligation) return notFound();

  const responsableOptions = mockUsers
    .filter((u) => u.tenantId === obligation.tenantId)
    .map((u) => ({ id: u.id, nombre: u.nombre }));

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Obligaciones', href: '/obligaciones' }, { label: obligation.nombre }]} />
      <ObligationDetailView obligation={obligation} responsableOptions={responsableOptions} />

      {/* La historia de una obligacion es la de sus tareas: cuando se
          completo cada una y con que evidencia. Se combinan en una sola linea
          de tiempo en vez de repartirlas por tarea. */}
      <HistorialTimeline
        entidadTipo="obligacion"
        entidadId={obligation.id}
        entidadesRelacionadas={obligation.tasks.map((t) => ({ tipo: 'tarea' as const, id: t.id }))}
        mostrarEntidad
        titulo="Historial de la obligacion"
        descripcionVacio="Cada tarea completada y cada evidencia cargada quedaran aqui con su autor y fecha."
      />
    </div>
  );
}
