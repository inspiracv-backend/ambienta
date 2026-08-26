/**
 * Que "nadie lo evaluó" no se muestre como "no cumple".
 *
 * ## El caso que lo motiva, visto en pantalla
 *
 * Al importar el articulado real de la BCN, el DS 1/2013 (reglamento del RETC)
 * entró con todos sus artículos en `N_E`. La pantalla de detalle mostró
 * **"No cumple · 0 %"**, y el listado de Matriz Legal lo mismo.
 *
 * Nadie había evaluado nada. El sistema le estaba diciendo a la empresa que
 * incumple una norma que **no había revisado todavía** — en la pantalla que
 * después se exporta a un auditor.
 *
 * La causa es de una línea: `computeNormCompliance` devuelve `0` cuando no hay
 * artículos evaluables, el mismo valor que devuelve cuando todo se evaluó y
 * todo salió NO. Un cero medido y un cero por ausencia de datos se veían igual.
 *
 * ## Por que ninguna prueba lo agarro
 *
 * `legal-matrix.test.ts` **sí** afirmaba `expect(computeNormCompliance(norma([])))
 * .toBe(0)`. Fijaba el valor de retorno sin preguntarse qué significaba, y
 * `normSemaforo(0) === 'no_cumple'` estaba en otra prueba, en otro `describe`.
 * Las dos en verde, y entre las dos el error. Ninguna miraba **lo que la
 * persona termina leyendo**, que es lo que importa acá.
 *
 * Por eso estas pruebas van hasta el semáforo y no se detienen en el número.
 */
import { describe, expect, it } from 'vitest';
import type { Articulo, LegalNorm } from '@ambienta/shared';
import {
  computeNormCompliance,
  computeNormComplianceOrNull,
  normSemaforo,
  normSemaforoDe,
  resumenDeNorma,
} from './legal-matrix';

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

/** Una norma recién traída de la BCN: articulado completo, cero evaluaciones. */
const RECIEN_IMPORTADA = norma([
  articulo({ id: 'a' }),
  articulo({ id: 'b' }),
  articulo({ id: 'c' }),
]);

/** La misma norma, evaluada entera y toda incumplida. */
const TODO_INCUMPLIDO = norma([
  articulo({ id: 'a', respuesta: 'NO' }),
  articulo({ id: 'b', respuesta: 'NO' }),
  articulo({ id: 'c', respuesta: 'NO' }),
]);

describe('sin evaluar no es incumplir', () => {
  it('el viejo calculo daba el MISMO numero para los dos casos', () => {
    // No es una prueba de regresión sino la demostración del defecto: mientras
    // `computeNormCompliance` siga existiendo —la usan los reportes y es el
    // espejo de la API— este empate sigue ahí, y por eso hace falta la otra.
    expect(computeNormCompliance(RECIEN_IMPORTADA)).toBe(0);
    expect(computeNormCompliance(TODO_INCUMPLIDO)).toBe(0);
  });

  it('sin nada evaluado no hay porcentaje, y eso se dice con null', () => {
    expect(computeNormComplianceOrNull(RECIEN_IMPORTADA)).toBeNull();
  });

  it('con todo evaluado y todo incumplido el cero SI es un cero medido', () => {
    expect(computeNormComplianceOrNull(TODO_INCUMPLIDO)).toBe(0);
  });

  it('los dos casos no pueden mostrar el mismo semaforo', () => {
    // **La afirmación que faltaba.** Es la que ve la persona.
    expect(normSemaforoDe(computeNormComplianceOrNull(RECIEN_IMPORTADA))).toBe('pendiente');
    expect(normSemaforoDe(computeNormComplianceOrNull(TODO_INCUMPLIDO))).toBe('no_cumple');
  });

  it('el semaforo viejo los pintaba iguales a los dos', () => {
    expect(normSemaforo(computeNormCompliance(RECIEN_IMPORTADA))).toBe('no_cumple');
    expect(normSemaforo(computeNormCompliance(TODO_INCUMPLIDO))).toBe('no_cumple');
  });

  it('una norma sin articulos tampoco incumple', () => {
    // Una norma del catálogo sin articulado importado. No haber traído el texto
    // no es un incumplimiento de la empresa.
    expect(normSemaforoDe(computeNormComplianceOrNull(norma([])))).toBe('pendiente');
  });

  it('un articulo excluido del calculo no alcanza para inventar un numero', () => {
    const n = norma([articulo({ id: 'a', respuesta: 'SI', incluidoEnCalculo: false })]);

    // Está evaluado, pero fuera del cálculo: no hay nada que promediar. Antes
    // esto daba 0 % y "No cumple" sobre un artículo que la empresa **cumple**.
    expect(computeNormComplianceOrNull(n)).toBeNull();
  });
});

describe('resumenDeNorma', () => {
  it('cuenta lo evaluado sobre lo aplicable, no sobre el total', () => {
    const n = norma([
      articulo({ id: 'a', respuesta: 'SI' }),
      articulo({ id: 'b', respuesta: 'NO' }),
      articulo({ id: 'c', respuesta: 'NA' }),
      articulo({ id: 'd' }),
    ]);

    const r = resumenDeNorma(n);

    expect(r.total).toBe(4);
    // El NA sale del denominador: un artículo que no rige no es uno pendiente.
    expect(r.aplicables).toBe(3);
    expect(r.evaluados).toBe(2);
    expect(r.sinEvaluar).toBe(1);
    expect(r.incumplidos).toBe(1);
    expect(r.pct).toBe(0.5);
  });

  it('en una norma recien importada el avance es cero y el pct no existe', () => {
    const r = resumenDeNorma(RECIEN_IMPORTADA);

    expect(r.evaluados).toBe(0);
    expect(r.aplicables).toBe(3);
    expect(r.pct).toBeNull();
  });

  it('una norma entera NA no tiene nada pendiente ni nada que calcular', () => {
    const r = resumenDeNorma(norma([articulo({ id: 'a', respuesta: 'NA' })]));

    expect(r.aplicables).toBe(0);
    expect(r.sinEvaluar).toBe(0);
    expect(r.pct).toBeNull();
  });
});
