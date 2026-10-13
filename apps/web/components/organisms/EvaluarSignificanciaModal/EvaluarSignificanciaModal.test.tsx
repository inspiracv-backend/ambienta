import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EvaluarSignificanciaModal } from './EvaluarSignificanciaModal';
import type { AspectoApi } from '@/lib/iso-store';

/**
 * El endpoint de significancia existía, estaba probado y **ninguna pantalla lo
 * llamaba**: todos los aspectos quedaban "Sin evaluar" y el filtro
 * "significativo sin tratar" no podía encontrar nada.
 */

const evaluar = vi.fn();
vi.mock('@/lib/iso-store', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/iso-store')>();
  return { ...real, useIso: () => ({ evaluarSignificancia: evaluar }) };
});

const ASPECTO = {
  id: 'a-1',
  actividad: 'Chancado',
  aspecto: 'Emisión de material particulado',
  puntajeFrecuencia: 8,
  puntajeSeveridad: 7,
  puntajeLegal: null,
} as unknown as AspectoApi;

beforeEach(() => {
  vi.clearAllMocks();
});

describe('evaluar un aspecto', () => {
  it('parte de los puntajes que ya tenía y manda los tres', async () => {
    evaluar.mockResolvedValue({ ok: true, significancia: 'significant', motivos: ['Frecuencia x severidad = 56, que alcanza el umbral de 25.'] });
    render(<EvaluarSignificanciaModal aspecto={ASPECTO} onOpenChange={vi.fn()} />);

    expect((screen.getByLabelText(/Frecuencia/) as HTMLSelectElement).value).toBe('8');
    // Sin puntaje legal guardado arranca en 1, no en el del medio: inventar un
    // requisito legal alto volvería significativo un aspecto que nadie evaluó.
    expect((screen.getByLabelText(/Requisito legal/) as HTMLSelectElement).value).toBe('1');

    await userEvent.click(screen.getByRole('button', { name: 'Evaluar' }));

    await waitFor(() => expect(evaluar).toHaveBeenCalled());
    expect(evaluar).toHaveBeenCalledWith('a-1', { frequency_score: 8, severity_score: 7, legal_score: 1 });
  });

  it('muestra el veredicto con sus motivos', async () => {
    evaluar.mockResolvedValue({
      ok: true,
      significancia: 'significant',
      motivos: ['Hay un requisito legal aplicable (nivel 9), y eso lo vuelve significativo aunque la magnitud sea baja.'],
    });
    render(<EvaluarSignificanciaModal aspecto={ASPECTO} onOpenChange={vi.fn()} />);

    await userEvent.click(screen.getByRole('button', { name: 'Evaluar' }));

    const caja = await screen.findByRole('status');
    expect(caja.textContent).toContain('Significativo');
    // El motivo es lo que se contesta en una auditoría: sin él, el veredicto es
    // un número sin explicación.
    expect(caja.textContent).toContain('requisito legal aplicable');
  });

  it('si la API rechaza, lo dice y no afirma ningún veredicto', async () => {
    evaluar.mockResolvedValue({ ok: false, error: 'legal_score tiene que estar entre 1 y 10; llego 0.' });
    render(<EvaluarSignificanciaModal aspecto={ASPECTO} onOpenChange={vi.fn()} />);

    await userEvent.click(screen.getByRole('button', { name: 'Evaluar' }));

    expect((await screen.findByRole('alert')).textContent).toContain('No se evaluó');
    expect(screen.queryByRole('status')).toBeNull();
  });
});
