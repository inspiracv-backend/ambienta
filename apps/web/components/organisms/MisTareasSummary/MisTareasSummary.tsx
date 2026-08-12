'use client';

import Link from 'next/link';
import type { User } from '@ambienta/shared';
import { AlertTriangle, CalendarClock, CheckCircle2, ListTodo } from 'lucide-react';
import { EmptyState, StatCard } from '@/components/molecules';
import { usePlanAccion } from '@/lib/plan-accion-store';
import { computeResumenUsuarioInterno } from '@/lib/role-dashboard';

function formatFecha(iso: string): string {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });
}

/**
 * "Mis tareas" del Usuario Interno (A2).
 *
 * RF-40 pide una vista de tareas asignadas por persona, y la matriz de
 * permisos le da las obligaciones "G (asignadas)" — no el panorama del
 * tenant completo. Antes veía el mismo resumen ejecutivo que el Admin
 * Empresa y tenía que buscar, entre todo lo de la empresa, qué le tocaba.
 *
 * Lo atrasado va primero y con tratamiento visual distinto: es lo que ya está
 * generando incumplimiento, no algo que "también hay que ver".
 */
export function MisTareasSummary({ user }: { user: User }) {
  const { plans } = usePlanAccion();
  const r = computeResumenUsuarioInterno(plans, user);

  const sinNada = r.planesAsignados.length === 0;

  return (
    <section aria-labelledby="mis-tareas" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="mis-tareas" className="text-sm font-semibold text-slate-900">
          Mis tareas
        </h2>
        <Link
          href="/calendario"
          className="text-xs font-medium text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          Ver calendario
        </Link>
      </div>

      {sinNada ? (
        <EmptyState
          icono={CheckCircle2}
          titulo="No tienes planes de acción asignados"
          descripcion="Cuando te asignen un plan de acción o una tarea, aparecerá aquí y en tu calendario."
        />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard
              etiqueta="Atrasadas"
              valor={r.atrasados.length}
              detalle={r.atrasados.length > 0 ? 'Fuera de plazo' : 'Nada fuera de plazo'}
              icono={AlertTriangle}
              tono={r.atrasados.length > 0 ? 'critico' : 'positivo'}
            />
            <StatCard
              etiqueta="Vencen esta semana"
              valor={r.proximos.length}
              detalle="Próximos 7 días"
              icono={CalendarClock}
              tono={r.proximos.length > 0 ? 'atencion' : 'neutro'}
            />
            <StatCard
              etiqueta="Tareas pendientes"
              valor={r.tareasPendientes}
              detalle={`de ${r.tareasTotales} en total`}
              icono={ListTodo}
            />
          </div>

          {(r.atrasados.length > 0 || r.proximos.length > 0) && (
            <div className="rounded-card border border-slate-200 bg-white p-4">
              <ul className="flex flex-col divide-y divide-slate-100">
                {[...r.atrasados, ...r.proximos].map((plan) => {
                  const atrasado = r.atrasados.includes(plan);
                  const pendientes = plan.tareas.filter((t) => !t.hecha).length;
                  return (
                    <li key={plan.id} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="min-w-0">
                        <Link
                          href={`/planes-accion/${plan.id}`}
                          className="block truncate text-sm font-medium text-slate-800 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                        >
                          {plan.titulo}
                        </Link>
                        <p className="truncate text-xs text-slate-500">
                          {plan.origenLabel}
                          {plan.tareas.length > 0 && ` · ${pendientes} de ${plan.tareas.length} tareas pendientes`}
                        </p>
                      </div>
                      <span
                        className={
                          atrasado
                            ? 'shrink-0 rounded-full bg-semaforo-no-cumple-bg px-2 py-0.5 text-xs font-semibold text-semaforo-no-cumple'
                            : 'shrink-0 rounded-full bg-semaforo-parcial-bg px-2 py-0.5 text-xs font-semibold text-semaforo-parcial'
                        }
                      >
                        {atrasado ? 'Venció ' : 'Vence '}
                        {formatFecha(plan.fechaLimite)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}
