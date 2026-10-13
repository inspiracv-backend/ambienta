'use client';

import { usePlanAccion } from '@/lib/plan-accion-store';
import { useNombreDeUsuario } from '@/lib/get-user-name';
import type { PlanAccionDetailViewProps } from './PlanAccionDetailView.types';
import { TareasDelPlanPanel } from './TareasDelPlanPanel';

const ESTADO_LABEL = { abierto: 'Abierto', en_progreso: 'En progreso', cerrado: 'Cerrado' } as const;

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** S-19 Detalle de Plan de Acción — vínculo con el artículo/tarea de origen (RF-19). */
export function PlanAccionDetailView({ plan: planProp }: PlanAccionDetailViewProps) {
  // Nombres de las personas reales; antes todo responsable salía «Sin asignar».
  const getUserName = useNombreDeUsuario();
  const { plans } = usePlanAccion();
  const plan = plans.find((p) => p.id === planProp.id) ?? planProp;

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Plan de Acción</span>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">{plan.titulo}</h1>
            <p className="mt-1 text-sm text-slate-500">
              Originado desde: <span className="font-medium text-slate-700">{plan.origenLabel}</span>
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Responsable: {getUserName(plan.responsableId)} · Vence {formatFecha(plan.fechaLimite)}
            </p>
          </div>
          <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
            {ESTADO_LABEL[plan.estado]}
          </span>
        </div>
      </div>

      {/* Las tareas volvieron el 14-sep con su modelo (#169, `db/31`). El
          recuadro "Historial de cambios — pendiente de modelar" no vuelve. */}
      <TareasDelPlanPanel planId={plan.id} />
    </div>
  );
}
