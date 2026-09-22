'use client';

import { Breadcrumbs } from '@/components/molecules';
import { FichaNoDisponible, HistorialTimeline, ObligationDetailView } from '@/components/organisms';
import { useObligations } from '@/lib/obligations-store';
import { usePersonasAsignables } from '@/lib/crm-etapas-store';

export default function ObligationDetailPage({ params }: { params: { id: string } }) {
  const { obligations, loading: cargandoObligaciones } = useObligations();
  // Personas de la base (`/users/`), no `mockUsers`: el responsable es una
  // clave foránea y un id de ejemplo hacía que la API rechazara la escritura.
  const { personas } = usePersonasAsignables();
  const obligation = obligations.find((o) => o.id === params.id);

  if (!obligation) return <FichaNoDisponible cargando={cargandoObligaciones} que="esta obligación" volverA="/obligaciones" volverEtiqueta="Volver a obligaciones" />;

  const responsableOptions = personas;

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
