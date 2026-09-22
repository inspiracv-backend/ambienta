'use client';

import { Breadcrumbs } from '@/components/molecules';
import { FichaNoDisponible, HistorialTimeline, PlanAccionDetailView } from '@/components/organisms';
import { usePlanAccion } from '@/lib/plan-accion-store';

export default function PlanAccionDetailPage({ params }: { params: { id: string } }) {
  const { plans, loading: cargandoPlanes } = usePlanAccion();
  const plan = plans.find((p) => p.id === params.id);

  if (!plan) return <FichaNoDisponible cargando={cargandoPlanes} que="este plan de acción" />;

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Plan de Acción', href: undefined }, { label: plan.titulo }]} />
      <PlanAccionDetailView plan={plan} />

      {/* El plan de accion es la evidencia de que se actuo sobre un
          incumplimiento (RF-30, RF-53): sin su historial no se puede
          demostrar cuando se hizo cada cosa. */}
      <HistorialTimeline
        entidadTipo="plan_accion"
        entidadId={plan.id}
        titulo="Historial del plan"
        descripcionVacio="Cada tarea completada y el cierre del plan quedaran aqui con su autor y fecha."
      />
    </div>
  );
}
