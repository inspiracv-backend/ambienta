import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { LegalNorm } from '@ambienta/shared';
import { LegalMatrixTable } from './LegalMatrixTable';

vi.mock('@/lib/get-user-name', () => ({ useNombreDeUsuario: () => () => 'Sin asignar' }));

const norma = (extra: Partial<LegalNorm>): LegalNorm =>
  ({
    id: 'n-1',
    tenantId: 't-1',
    plantIds: [],
    tipoDocumento: 'Ley',
    nombre: 'Ley 19.300',
    fuente: 'BCN',
    articulos: [],
    ...extra,
  }) as LegalNorm;

function fila(nombre: string) {
  return screen.getByRole('link', { name: nombre }).closest('tr')!;
}

describe('la cobertura de una norma', () => {
  it('sin articulado no dice 100 %: dice que no hay articulado', () => {
    // `computeNormCoverage` da 1 sobre cero articulos. En la tabla eso se leia
    // "100 %", o sea "se reviso todo", para una norma cuyo texto no se cargo.
    render(<LegalMatrixTable norms={[norma({ nombre: 'RCA sin texto' })]} plants={[]} />);

    const celdas = within(fila('RCA sin texto'));
    expect(celdas.getByText('Sin articulado')).toBeTruthy();
    expect(celdas.queryByText('100%')).toBeNull();
  });

  it('con articulado evaluado entero, si dice 100 %', () => {
    render(
      <LegalMatrixTable
        norms={[
          norma({
            nombre: 'DS 40',
            articulos: [
              { id: 'a-1', normId: 'n-1', numero: '1', descripcion: '', respuesta: 'SI', incluidoEnCalculo: true },
            ] as LegalNorm['articulos'],
          }),
        ]}
        plants={[]}
      />,
    );

    // Cumplimiento y cobertura valen 100 % los dos: dos celdas.
    expect(within(fila('DS 40')).getAllByText('100%')).toHaveLength(2);
  });
});
