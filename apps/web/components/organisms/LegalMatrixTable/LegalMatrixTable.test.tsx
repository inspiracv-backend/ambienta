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

describe('una norma que no aplica o que ya no rige', () => {
  const articulosSinEvaluar = Array.from({ length: 3 }, (_, i) => ({
    id: `x-${i}`,
    normId: 'n-2',
    numero: `${i + 1}`,
    descripcion: '',
    respuesta: 'N_E',
    incluidoEnCalculo: true,
  })) as LegalNorm['articulos'];

  it('si la matriz dice que no aplica, lo dice y no pide evaluarla', () => {
    // La Ley 20.920 de la empresa de prueba: marcada no aplicable por la
    // sincronizacion y conservada. Salia "Pendiente de evaluar · 61 sin evaluar".
    render(
      <LegalMatrixTable
        norms={[
          norma({
            id: 'n-2',
            nombre: 'Ley 20.920',
            articulos: articulosSinEvaluar,
            aplicabilidad: {
              determinadaPor: 'automatica',
              estado: 'no_aplica',
              criterio: 'El calculo por sector dejo de incluirla.',
              actividadesEconomicas: [],
              aspectoAmbientalIds: [],
            },
          }),
        ]}
        plants={[]}
      />,
    );

    const celdas = within(fila('Ley 20.920'));
    expect(celdas.getByText('No aplica')).toBeTruthy();
    expect(celdas.getByText('El calculo por sector dejo de incluirla.')).toBeTruthy();
    expect(celdas.queryByText(/sin evaluar/)).toBeNull();
    expect(celdas.queryByText('Pendiente de evaluar')).toBeNull();
  });

  it('una norma derogada lleva la etiqueta', () => {
    render(
      <LegalMatrixTable norms={[norma({ nombre: 'DS viejo', vigencia: { estado: 'derogada' } })]} plants={[]} />,
    );
    expect(within(fila('DS viejo')).getByText('Derogada')).toBeTruthy();
  });
});

