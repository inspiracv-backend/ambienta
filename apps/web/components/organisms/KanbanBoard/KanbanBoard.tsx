'use client';

import type { ObligationStatus } from '@ambienta/shared';
import { StatusBadge } from '@/components/atoms';
import { getUserName } from '@/lib/get-user-name';
import type { KanbanBoardProps } from './KanbanBoard.types';

const COLUMNS: { estado: ObligationStatus; label: string }[] = [
  { estado: 'vigente', label: 'Vigente' },
  { estado: 'por_vencer', label: 'Por vencer' },
  { estado: 'sin_evidencia', label: 'Sin evidencia' },
  { estado: 'vencida', label: 'Vencida' },
];

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });
}

/**
 * S-18 Kanban de Tareas. Columnas por estado (H4: mismos 4 estados de
 * `ObligationStatus`, no una taxonomía paralela) — ver gap en
 * seccion-f-calendario-gantt-kanban.md.
 */
export function KanbanBoard({ tickets, onSelectTicket }: KanbanBoardProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {COLUMNS.map((col) => {
        const columnTickets = tickets.filter((t) => t.task.estado === col.estado);
        return (
          <div key={col.estado} className="flex flex-col gap-2 rounded-card border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{col.label}</h3>
              <span className="text-xs text-slate-400">{columnTickets.length}</span>
            </div>
            <div className="flex flex-col gap-2">
              {columnTickets.length === 0 ? (
                <p className="rounded-lg border border-dashed border-slate-200 p-3 text-center text-xs text-slate-400">Sin tareas</p>
              ) : (
                columnTickets.map((t) => (
                  <button
                    key={t.task.id}
                    type="button"
                    onClick={() => onSelectTicket(t)}
                    className="rounded-lg border border-slate-200 bg-white p-3 text-left text-sm shadow-sm hover:border-brand-300"
                  >
                    <p className="font-medium text-slate-800">{t.task.titulo}</p>
                    <p className="mt-0.5 text-xs text-slate-500">{t.obligation.nombre}</p>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-xs text-slate-500">{formatFecha(t.task.vencimiento)} · {getUserName(t.task.responsableId)}</span>
                      <StatusBadge status={t.task.estado} />
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
