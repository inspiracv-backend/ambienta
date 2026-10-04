import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CalendarMonthView } from './CalendarMonthView';
import type { EventoDeCalendario } from '@/lib/eventos-de-calendario';

/**
 * Revisiones de normas e inscripciones de equipos en el calendario (ISO 14001,
 * "Calendario: vencimientos de evaluación periódica").
 */

function evento(over: Partial<EventoDeCalendario> & { id: string; fecha: string }): EventoDeCalendario {
  return { titulo: 'DS 90', tipo: 'revision_norma', href: '/matriz-legal', vencido: false, ...over };
}

beforeEach(() => {
  // El mes que se ve depende de hoy: se fija para que la prueba no cambie con la fecha.
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 8, 15, 12, 0));
});

afterEach(() => {
  vi.useRealTimers();
});

/** La celda del calendario que muestra este numero de dia del mes en curso. */
function celdaDelDia(dia: number): HTMLElement {
  const celdas = screen
    .getAllByText(String(dia), { selector: 'span' })
    .map((s) => s.parentElement as HTMLElement)
    .filter((c) => !c.className.includes('bg-slate-50'));
  expect(celdas).toHaveLength(1);
  return celdas[0];
}

describe('los eventos que no son tareas', () => {
  it('caen en su dia, no en el anterior', () => {
    // Con `new Date('2026-09-02')` seria medianoche UTC: el 1 de septiembre en Chile.
    render(<CalendarMonthView tickets={[]} onSelectTicket={vi.fn()} eventos={[evento({ id: 'r1', fecha: '2026-09-02' })]} />);

    const enlace = screen.getByRole('link', { name: 'Revisión: DS 90' });
    expect(celdaDelDia(2).contains(enlace)).toBe(true);
    expect(celdaDelDia(1).contains(enlace)).toBe(false);
  });

  it('llevan a su pantalla, no abren un ticket', () => {
    const onSelect = vi.fn();
    render(
      <CalendarMonthView
        tickets={[]}
        onSelectTicket={onSelect}
        eventos={[evento({ id: 'e1', fecha: '2026-09-10', tipo: 'inscripcion_equipo', titulo: 'Caldera 1', href: '/equipos-regulados' })]}
      />,
    );

    expect(screen.getByRole('link', { name: 'Vence inscripción: Caldera 1' }).getAttribute('href')).toBe(
      '/equipos-regulados',
    );
  });

  it('cuentan en el "+N más" del dia', () => {
    const eventos = ['a', 'b', 'c', 'd', 'e'].map((id) => evento({ id, fecha: '2026-09-20', titulo: `Norma ${id}` }));
    render(<CalendarMonthView tickets={[]} onSelectTicket={vi.fn()} eventos={eventos} />);

    expect(screen.getByText('+2 más')).toBeTruthy();
  });
});
