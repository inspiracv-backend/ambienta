'use client';

import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/atoms';
import { cn } from '@/lib/utils';
import type { CalendarMonthViewProps } from './CalendarMonthView.types';

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

const ESTADO_DOT: Record<string, string> = {
  vigente: 'bg-semaforo-cumple',
  por_vencer: 'bg-semaforo-parcial',
  vencida: 'bg-semaforo-no-cumple',
  sin_evidencia: 'bg-semaforo-no-cumple',
};

function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** S-16 Calendario. Al hacer clic en un evento se abre el mismo ticket que en Obligaciones (H4). */
export function CalendarMonthView({ tickets, onSelectTicket }: CalendarMonthViewProps) {
  const [cursor, setCursor] = useState(() => new Date());

  const days = useMemo(() => {
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const firstOfMonth = new Date(year, month, 1);
    const startOffset = (firstOfMonth.getDay() + 6) % 7; // lunes=0
    const gridStart = new Date(year, month, 1 - startOffset);

    return Array.from({ length: 42 }, (_, i) => {
      const date = new Date(gridStart);
      date.setDate(gridStart.getDate() + i);
      return date;
    });
  }, [cursor]);

  function changeMonth(delta: number) {
    setCursor((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));
  }

  return (
    <div className="rounded-card border border-slate-200 bg-white p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">
          {MESES[cursor.getMonth()]} {cursor.getFullYear()}
        </h2>
        <div className="flex gap-1">
          <Button variant="ghost" size="md" aria-label="Mes anterior" onClick={() => changeMonth(-1)}>
            <ChevronLeft className="h-4 w-4" aria-hidden />
          </Button>
          <Button variant="ghost" size="md" onClick={() => setCursor(new Date())}>
            Hoy
          </Button>
          <Button variant="ghost" size="md" aria-label="Mes siguiente" onClick={() => changeMonth(1)}>
            <ChevronRight className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-slate-100 bg-slate-100 text-xs">
        {DIAS.map((d) => (
          <div key={d} className="bg-slate-50 px-2 py-1.5 text-center font-medium text-slate-500">
            {d}
          </div>
        ))}
        {days.map((date) => {
          const dayTickets = tickets.filter((t) => sameDay(new Date(t.task.vencimiento), date));
          const isCurrentMonth = date.getMonth() === cursor.getMonth();
          const isToday = sameDay(date, new Date());

          return (
            <div key={date.toISOString()} className={cn('min-h-[92px] bg-white p-1.5', !isCurrentMonth && 'bg-slate-50 text-slate-400')}>
              <span className={cn('inline-flex h-5 w-5 items-center justify-center rounded-full text-xs', isToday && 'bg-brand-600 font-semibold text-white')}>
                {date.getDate()}
              </span>
              <ul className="mt-1 flex flex-col gap-0.5">
                {dayTickets.slice(0, 3).map((t) => (
                  <li key={t.task.id}>
                    <button
                      type="button"
                      onClick={() => onSelectTicket(t)}
                      className="flex w-full items-center gap-1 truncate rounded px-1 py-0.5 text-left text-[11px] text-slate-700 hover:bg-slate-100"
                    >
                      <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', ESTADO_DOT[t.task.estado])} aria-hidden />
                      <span className="truncate">{t.task.titulo}</span>
                    </button>
                  </li>
                ))}
                {dayTickets.length > 3 && (
                  <li className="px-1 text-[10px] text-slate-400">+{dayTickets.length - 3} más</li>
                )}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
