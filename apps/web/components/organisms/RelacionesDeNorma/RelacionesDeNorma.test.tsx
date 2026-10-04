import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RelacionesDeNorma } from './RelacionesDeNorma';

const get = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return { ...real, api: { get: (...a: unknown[]) => get(...a) } };
});

beforeEach(() => vi.clearAllMocks());

describe('las relaciones de una norma', () => {
  it('se leen desde esta norma: quien la modifica y a quien modifica ella', async () => {
    get.mockResolvedValue([
      {
        relation_type: 'modifica',
        sentido: 'entrante',
        norm_id: 'n-3592',
        norm_type: 'decreto_supremo',
        norm_number: '3592',
        title: 'MODIFICA DECRETO Nº 609',
        publication_date: '2000-09-26',
      },
      {
        relation_type: 'reglamenta',
        sentido: 'saliente',
        norm_id: 'n-x',
        norm_type: 'ley',
        norm_number: '19300',
        title: 'BASES',
        publication_date: null,
      },
    ]);
    render(<RelacionesDeNorma normId="n-609" tenantId="t-1" />);

    expect(await screen.findByText('Modificada por')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'D.S. 3592 (2000)' }).getAttribute('href')).toBe('/matriz-legal/n-3592');
    expect(screen.getByText('Reglamenta a')).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/catalog/norms/n-609/relations', { tenantId: 't-1' });
  });

  it('sin relaciones lo dice, en vez de dejar la seccion vacia', async () => {
    get.mockResolvedValue([]);
    render(<RelacionesDeNorma normId="n-1" tenantId="t-1" />);
    expect(await screen.findByText(/no registra relaciones/)).toBeTruthy();
  });

  it('si no se pudo preguntar, lo dice: no es lo mismo que no tener relaciones', async () => {
    get.mockRejectedValue(new Error('sin red'));
    render(<RelacionesDeNorma normId="n-1" tenantId="t-1" />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/No se pudieron cargar/);
    expect(screen.queryByText(/no registra relaciones/)).toBeNull();
  });
});
