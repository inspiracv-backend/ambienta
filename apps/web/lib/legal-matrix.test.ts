import { describe, expect, it } from 'vitest';
import type { Articulo, LegalNorm } from '@ambienta/shared';
import {
  articuloSemaforo,
  computeNormCompliance,
  countArticulosEnIncumplimiento,
  normSemaforo,
} from './legal-matrix';

/**
 * El % de cumplimiento es el número que la empresa mira para decidir dónde
 * poner recursos, y el que aparece en los reportes de auditoría (RF-24, RF-58).
 * Que NA y N_E queden fuera del denominador no es un detalle: si contaran,
 * una norma con muchos artículos no aplicables se vería como incumplimiento.
 */

function articulo(over: Partial<Articulo> = {}): Articulo {
  return {
    id: 'art-1',
    numero: 'Art. 1',
    texto: 'Texto del artículo',
    respuesta: 'N_E',
    formaCumplimiento: '',
    responsableId: null,
    evidenciaUrl: null,
    incluidoEnCalculo: true,
    ...over,
  } as Articulo;
}

function norma(articulos: Articulo[]): LegalNorm {
  return { id: 'norm-1', articulos } as LegalNorm;
}

describe('computeNormCompliance', () => {
  it('cuenta solo SI y NO en el denominador', () => {
    const n = norma([
      articulo({ id: 'a', respuesta: 'SI' }),
      articulo({ id: 'b', respuesta: 'NO' }),
      articulo({ id: 'c', respuesta: 'NA' }),
      articulo({ id: 'd', respuesta: 'N_E' }),
    ]);
    // 1 de 2 evaluables, no 1 de 4.
    expect(computeNormCompliance(n)).toBe(0.5);
  });

  it('excluye los artículos marcados fuera del cálculo (RF-24)', () => {
    const n = norma([
      articulo({ id: 'a', respuesta: 'SI', incluidoEnCalculo: true }),
      articulo({ id: 'b', respuesta: 'NO', incluidoEnCalculo: false }),
    ]);
    expect(computeNormCompliance(n)).toBe(1);
  });

  it('devuelve 0 cuando no hay nada evaluado todavía', () => {
    // Norma recién cargada: todos los artículos en N_E. No es "0% de
    // cumplimiento" real, pero es el valor conservador y así lo espera S-11.
    expect(computeNormCompliance(norma([articulo(), articulo({ id: 'b' })]))).toBe(0);
  });

  it('devuelve 0 en una norma sin artículos', () => {
    expect(computeNormCompliance(norma([]))).toBe(0);
  });

  it('devuelve 1 cuando todo lo evaluable cumple', () => {
    const n = norma([
      articulo({ id: 'a', respuesta: 'SI' }),
      articulo({ id: 'b', respuesta: 'SI' }),
      articulo({ id: 'c', respuesta: 'NA' }),
    ]);
    expect(computeNormCompliance(n)).toBe(1);
  });
});

describe('countArticulosEnIncumplimiento', () => {
  it('cuenta los NO, sin importar si entran en el cálculo', () => {
    // Un artículo excluido del % sigue siendo un incumplimiento real que hay
    // que mostrar: excluirlo del cálculo no lo hace desaparecer.
    const n = norma([
      articulo({ id: 'a', respuesta: 'NO', incluidoEnCalculo: true }),
      articulo({ id: 'b', respuesta: 'NO', incluidoEnCalculo: false }),
      articulo({ id: 'c', respuesta: 'SI' }),
    ]);
    expect(countArticulosEnIncumplimiento(n)).toBe(2);
  });
});

describe('articuloSemaforo', () => {
  it('mapea cada respuesta a su color', () => {
    expect(articuloSemaforo('SI')).toBe('cumple');
    expect(articuloSemaforo('NO')).toBe('no_cumple');
    expect(articuloSemaforo('NA')).toBe('na');
    expect(articuloSemaforo('N_E')).toBe('pendiente');
  });
});

describe('normSemaforo', () => {
  it('usa los umbrales 80% y 50%', () => {
    expect(normSemaforo(1)).toBe('cumple');
    expect(normSemaforo(0.8)).toBe('cumple');
    expect(normSemaforo(0.79)).toBe('parcial');
    expect(normSemaforo(0.5)).toBe('parcial');
    expect(normSemaforo(0.49)).toBe('no_cumple');
    expect(normSemaforo(0)).toBe('no_cumple');
  });
});
