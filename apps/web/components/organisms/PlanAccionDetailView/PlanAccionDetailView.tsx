'use client';

import { CheckSquare, Square } from 'lucide-react';
import { usePlanAccion } from '@/lib/plan-accion-store';
import { getUserName } from '@/lib/get-user-name';
import type { PlanAccionDetailViewProps } from './PlanAccionDetailView.types';

const ESTADO_LABEL = { abierto: 'Abierto', en_progreso: 'En progreso', cerrado: 'Cerrado' } as const;

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** S-19 Detalle de Plan de Acción — vínculo con el artículo/tarea de origen (RF-19). */
export function PlanAccionDetailView({ plan: planProp }: PlanAccionDetailViewProps) {
  const { plans, toggleTarea } = usePlanAccion();
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

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Tareas del plan</h2>
        {plan.tareas.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            Este plan aún no tiene tareas registradas.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {plan.tareas.map((tarea) => (
              <li key={tarea.id}>
                <button
                  type="button"
                  onClick={() => toggleTarea(plan.id, tarea.id)}
                  aria-pressed={tarea.hecha}
                  className="flex w-full items-center gap-2 rounded-lg border border-slate-100 px-3 py-2 text-left text-sm hover:bg-slate-50"
                >
                  {tarea.hecha ? (
                    <CheckSquare className="h-4 w-4 shrink-0 text-brand-600" aria-hidden />
                  ) : (
                    <Square className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                  )}
                  <span className={tarea.hecha ? 'text-slate-400 line-through' : 'text-slate-700'}>{tarea.titulo}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-card border border-dashed border-slate-300 bg-white p-4 text-xs text-slate-400">
        Historial de cambios — pendiente de modelar (audit log transversal a Matriz Legal, Obligaciones y Planes de Acción).
      </div>
    </div>
  );
}
