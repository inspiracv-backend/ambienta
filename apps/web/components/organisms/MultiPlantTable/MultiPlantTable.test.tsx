/**
 * Lo que el Admin Empresa lee en el tablero multi-planta (#125, RF-54/RF-55).
 *
 * **Este archivo no existía**, y por eso el "0 %" de las plantas sin evaluar
 * llegó a la pantalla ejecutiva. `dashboard-metrics.test.ts` cubría el cálculo;
 * lo que nadie probaba era el componente que lo pinta — que además decide el
 * **orden**, y ahí estaba la segunda mitad del problema: una planta sin datos
 * ordenada como si valiera cero encabeza la lista y tapa los problemas reales.
 *
 * Todas las afirmaciones son sobre texto visible y sobre el orden en el DOM.
 */
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import type { PlantMetric } from '@/lib/dashboard-metrics';
import { MultiPlantTable } from './MultiPlantTable';

function metrica(
  nombre: string,
  cumplimientoPct: number | null,
  over: Partial<PlantMetric> = {},
): PlantMetric {
  return {
    plant: { id: nombre, nombre, comuna: 'Comuna', region: 'RM' },
    cumplimientoPct,
    incumplimientos: 0,
    noConformidadesActivas: 0,
    proximoVencimiento: null,
    ...over,
  };
}

/** La tabla de escritorio; las tarjetas de mobile repiten los mismos datos. */
function tabla() {
  return within(screen.getByRole('table'));
}

describe('una planta que nadie evaluo', () => {
  it('NO dice que su cumplimiento es 0%', () => {
    // La afirmación central. En el seed son dos de tres plantas.
    render(<MultiPlantTable metrics={[metrica('Faena Antofagasta', null)]} />);

    expect(tabla().queryByText('0%')).not.toBeInTheDocument();
  });

  it('NO la pinta como incumplida', () => {
    render(<MultiPlantTable metrics={[metrica('Faena Antofagasta', null)]} />);

    expect(tabla().queryByText('No cumple')).not.toBeInTheDocument();
    expect(tabla().getByText('Pendiente de evaluar')).toBeInTheDocument();
  });

  it('dice "Sin evaluar", que es lo que pasa', () => {
    render(<MultiPlantTable metrics={[metrica('Faena Antofagasta', null)]} />);

    expect(tabla().getByText('Sin evaluar')).toBeInTheDocument();
  });
});

describe('el orden', () => {
  it('pone el peor cumplimiento primero', () => {
    render(
      <MultiPlantTable
        metrics={[metrica('Buena', 0.9), metrica('Mala', 0.2), metrica('Regular', 0.6)]}
      />,
    );

    const filas = tabla().getAllByRole('row').slice(1);
    expect(filas.map((f) => within(f).getAllByRole('cell')[0]!.textContent)).toEqual([
      'Mala',
      'Regular',
      'Buena',
    ]);
  });

  it('deja las plantas sin evaluar al FINAL, no arriba', () => {
    // **La segunda mitad del error.** Ordenadas como ceros encabezaban la
    // tabla, que es el lugar reservado a lo urgente: el tablero abría
    // señalando incógnitas y empujaba hacia abajo el incumplimiento real.
    render(
      <MultiPlantTable
        metrics={[metrica('Sin datos', null), metrica('Mala', 0.2), metrica('Buena', 0.9)]}
      />,
    );

    const filas = tabla().getAllByRole('row').slice(1);
    expect(filas.map((f) => within(f).getAllByRole('cell')[0]!.textContent)).toEqual([
      'Mala',
      'Buena',
      'Sin datos',
    ]);
  });

  it('no revienta con todas las plantas sin evaluar', () => {
    // Una empresa recién puesta en marcha está exactamente así.
    render(
      <MultiPlantTable metrics={[metrica('A', null), metrica('B', null)]} />,
    );

    expect(tabla().getAllByText('Sin evaluar')).toHaveLength(2);
  });
});

describe('un cero medido sigue siendo un cero', () => {
  it('una planta evaluada y sin nada cumplido dice 0% y "No cumple"', () => {
    // Arreglar el falso positivo no puede tapar el incumplimiento real.
    render(<MultiPlantTable metrics={[metrica('Planta Calama', 0)]} />);

    expect(tabla().getByText('0%')).toBeInTheDocument();
    expect(tabla().getByText('No cumple')).toBeInTheDocument();
  });

  it('y va antes que una sin evaluar', () => {
    render(
      <MultiPlantTable metrics={[metrica('Sin datos', null), metrica('Cero real', 0)]} />,
    );

    const filas = tabla().getAllByRole('row').slice(1);
    expect(within(filas[0]!).getAllByRole('cell')[0]!.textContent).toBe('Cero real');
  });
});
