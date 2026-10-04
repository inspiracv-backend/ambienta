import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { UltimaSincronizacionBcn } from './UltimaSincronizacionBcn';

/** De dónde salió el catálogo y cuándo (ingesta-normativa-bcn). */

const get = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return { ...real, api: { get: (...a: unknown[]) => get(...a) } };
});

beforeEach(() => get.mockReset());

describe('UltimaSincronizacionBcn', () => {
  it('sin corridas dice que nunca se sincronizó, no que está al día', async () => {
    get.mockResolvedValue([]);
    render(<UltimaSincronizacionBcn />);
    expect(await screen.findByText(/todavía no registra ninguna sincronización/)).toBeInTheDocument();
  });

  it('una corrida parcial dice qué no encontró', async () => {
    get.mockResolvedValue([
      { id: 1, started_at: '2026-09-14T10:00:00Z', finished_at: '2026-09-14T10:05:00Z', status: 'partial',
        norms_created: 2, norms_updated: 5, response_metadata: { sin_su_norma: ['ruidos (esperaba 38)'] } },
    ]);
    render(<UltimaSincronizacionBcn />);
    expect(await screen.findByText('parcial')).toBeInTheDocument();
    expect(screen.getByText(/no se encontró: ruidos \(esperaba 38\)/)).toBeInTheDocument();
  });

});
