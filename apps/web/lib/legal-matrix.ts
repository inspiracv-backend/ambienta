import type { Articulo, LegalNorm } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms';

/**
 * % de cumplimiento de una norma = SI / (SI + NO) entre los artículos marcados
 * `incluidoEnCalculo` (RF-13, S-11) — NA y N_E (pendiente de evaluar) no cuentan
 * en el denominador. Réplica en el frontend de la vista SQL
 * `resumen_cumplimiento_requisito` documentada en el ADD (docs/arquitectura).
 *
 * ## Su equivalente en la API se llama distinto, a propósito
 *
 * Es `porcentaje_sobre_evaluados` en `GET /compliance/matrices/{id}/resumen`.
 * **No es `porcentaje`.** Ese otro es el conservador —cuenta lo pendiente como
 * no cumplido— y da un número más bajo sobre los mismos datos: una empresa con
 * un artículo cumplido y diecinueve sin evaluar sale 100 % acá y 5 % allá.
 *
 * Los dos son correctos y responden preguntas distintas. Lo que sería un error
 * es cambiar el denominador de solo uno de los dos lados: **si esta función
 * cambia, `apps/api/app/services/resumen_cumplimiento.py` tiene que cambiar
 * con ella**, o la pantalla y el informe dirán cosas distintas sobre la misma
 * empresa sin que nada lo señale.
 */
export function computeNormCompliance(norm: LegalNorm): number {
  const evaluables = norm.articulos.filter((a) => a.incluidoEnCalculo && (a.respuesta === 'SI' || a.respuesta === 'NO'));
  if (evaluables.length === 0) return 0;
  const cumplidos = evaluables.filter((a) => a.respuesta === 'SI').length;
  return cumplidos / evaluables.length;
}

/**
 * % de cobertura = artículos evaluados / artículos aplicables.
 *
 * Es un indicador distinto del cumplimiento y hace falta porque el cumplimiento
 * solo mira lo que ya se evaluó: una norma con un artículo en SI y quince sin
 * evaluar muestra 100%, que es cierto sobre la muestra y engañoso sobre la
 * norma. Kawak resuelve lo mismo contando lo no calificado como cero; acá se
 * prefiere mostrar los dos números, porque cada uno responde una pregunta
 * distinta — "¿cumplimos?" y "¿cuánto alcanzamos a revisar?".
 *
 * `NA` sale de ambos denominadores: un artículo no aplicable no es un artículo
 * sin revisar. `incluidoEnCalculo` no se aplica acá a propósito: excluir algo
 * del cálculo de cumplimiento es una decisión legítima, esconderlo de la
 * cobertura sería tapar que nadie lo miró.
 *
 * En la API es `cobertura`, del mismo endpoint. Misma advertencia que arriba:
 * las dos definiciones tienen que moverse juntas.
 */
export function computeNormCoverage(norm: LegalNorm): number {
  const aplicables = norm.articulos.filter((a) => a.respuesta !== 'NA');
  if (aplicables.length === 0) return 1;
  const evaluados = aplicables.filter((a) => a.respuesta !== 'N_E').length;
  return evaluados / aplicables.length;
}

/** Artículos aplicables que nadie evaluó todavía. */
export function countArticulosSinEvaluar(norm: LegalNorm): number {
  return norm.articulos.filter((a) => a.respuesta === 'N_E').length;
}

export function countArticulosEnIncumplimiento(norm: LegalNorm): number {
  return norm.articulos.filter((a) => a.respuesta === 'NO').length;
}

export function articuloSemaforo(respuesta: Articulo['respuesta']): SemaforoStatus {
  switch (respuesta) {
    case 'SI':
      return 'cumple';
    case 'NO':
      return 'no_cumple';
    case 'NA':
      return 'na';
    case 'N_E':
    default:
      return 'pendiente';
  }
}

export function normSemaforo(pct: number): SemaforoStatus {
  if (pct >= 0.8) return 'cumple';
  if (pct >= 0.5) return 'parcial';
  return 'no_cumple';
}
