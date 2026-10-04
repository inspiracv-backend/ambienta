import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AspectosSinTratarResumen } from './AspectosSinTratarResumen';
import { ApiError } from '@/lib/api-client';

/** Los aspectos significativos sin tratar, en el tablero (ISO 14001 §6.1.4). */

const get = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return { ...real, api: { get: (...a: unknown[]) => get(...a) } };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('el resumen de aspectos sin tratar', () => {
  it('cuenta los que devuelve la misma vista que el panel de aspectos', async () => {
    get.mockResolvedValue([{ id: 'a1' }, { id: 'a2' }]);

    render(<AspectosSinTratarResumen tenantId="t1" />);

    expect(await screen.findByText('2')).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/iso14001/aspects/significant-untreated', { tenantId: 't1' });
    expect(screen.getByRole('link').getAttribute('href')).toBe('/aspectos-ambientales');
  });

  it('cero es un dato y se muestra como tal', async () => {
    get.mockResolvedValue([]);

    render(<AspectosSinTratarResumen tenantId="t1" />);

    expect(await screen.findByText('0')).toBeTruthy();
    expect(screen.getByText('Todos los aspectos significativos tienen tratamiento')).toBeTruthy();
  });

  it('si no se pudo preguntar lo dice, en vez de mostrar un cero', async () => {
    get.mockRejectedValue(new ApiError(500, 'Error', null));

    render(<AspectosSinTratarResumen tenantId="t1" />);

    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByText('0')).toBeNull();
  });

  it('sin permiso no aparece: no es un modulo de esa persona', async () => {
    get.mockRejectedValue(new ApiError(403, 'Forbidden', null));

    const { container } = render(<AspectosSinTratarResumen tenantId="t1" />);

    await vi.waitFor(() => expect(get).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(container.textContent).toBe('');
  });
});
