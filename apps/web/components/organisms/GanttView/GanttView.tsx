'use client';

import { useMemo } from 'react';
import { getUserName } from '@/lib/get-user-name';
import { cn } from '@/lib/utils';
import type { GanttViewProps } from './GanttView.types';

const ESTADO_BAR: Record<string, string> = {
  vigente: 'bg-semaforo-cumple',
  por_vencer: 'bg-semaforo-parcial',
  vencida: 'bg-semaforo-no-cumple',
  sin_evidencia: 'bg-semaforo-no-cumple',
};

/**
 * S-17 Vista Gantt — construida automáticamente desde las fechas de las
 * tareas (RF-28). Barras proporcionales dentro de una ventana móvil de 90
 * días (-7 a +83 desde hoy) en vez de una librería de Gantt de terceros.
 */
export function GanttView({ tickets, onSelectTicket }: GanttViewProps) {
  const rangeStart = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d;
  }, []);
  const rangeDays = 90;

  const sorted = useMemo(
    () => [...tickets].sort((a, b) => new Date(a.task.vencimiento).getTime() - new Date(b.task.vencimiento).getTime()),
    [tickets],
  );

  function offsetPct(iso: string) {
    const days = (new Date(iso).getTime() - rangeStart.getTime()) / (1000 * 60 * 60 * 24);
    return Math.min(Math.max((days / rangeDays) * 100, 0), 96);
  }

  if (sorted.length === 0) {
    return (
      <div className="rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
        No hay tareas en el rango visible.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-card border border-slate-200 bg-white p-4">
      <p className="mb-3 text-xs text-slate-500">
        Ventana: {rangeStart.toLocaleDateString('es-CL')} — {new Date(rangeStart.getTime() + rangeDays * 86400000).toLocaleDateString('es-CL')}
      </p>
      <ul className="flex min-w-[640px] flex-col gap-2">
        {sorted.map((t) => (
          <li key={t.task.id} className="flex items-center gap-3">
            <div className="w-48 shrink-0 truncate text-sm text-slate-700">{t.task.titulo}</div>
            <div className="relative h-6 flex-1 rounded bg-slate-50">
              <button
                type="button"
                onClick={() => onSelectTicket(t)}
                title={`${t.task.titulo} — ${getUserName(t.task.responsableId)}`}
                style={{ left: `${offsetPct(t.task.vencimiento)}%` }}
                className={cn('absolute top-0.5 h-5 w-16 rounded text-left text-[10px] text-white', ESTADO_BAR[t.task.estado])}
              >
                <span className="sr-only">{t.task.titulo}</span>
              </button>
            </div>
            <span className="w-28 shrink-0 text-right text-xs text-slate-500">{getUserName(t.task.responsableId)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
