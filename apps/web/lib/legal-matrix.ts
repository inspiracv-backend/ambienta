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

/**
 * Lo mismo que `computeNormCompliance`, pero **distingue "no cumple" de "nadie
 * lo miró"** — que es la diferencia entre un hecho y una acusación falsa.
 *
 * `computeNormCompliance` devuelve `0` en los dos casos: cuando todo se evaluó
 * y todo salió NO, y cuando no se evaluó nada. Con el catálogo sembrado eso no
 * se notaba; con el articulado real de la BCN, una norma recién importada llega
 * con sus 210 artículos en `N_E` y la pantalla la pintaba **"No cumple, 0 %"**.
 *
 * Es exactamente el error que este repo se cansa de advertir, y acá es el peor
 * de todos: **le dice a una empresa que incumple una norma que nadie reviso**.
 * Un cero que se ve idéntico a un cero medido, en la pantalla que después se
 * exporta a un auditor.
 *
 * Devuelve `null` cuando no hay nada que medir. Quien lo use tiene que decidir
 * qué mostrar, que es justamente lo que obliga a no inventar un número.
 */
export function computeNormComplianceOrNull(norm: LegalNorm): number | null {
  const evaluables = norm.articulos.filter(
    (a) => a.incluidoEnCalculo && (a.respuesta === 'SI' || a.respuesta === 'NO'),
  );
  if (evaluables.length === 0) return null;
  return evaluables.filter((a) => a.respuesta === 'SI').length / evaluables.length;
}

/** El semáforo de una norma, con `null` —nada evaluado— como `pendiente`. */
export function normSemaforoDe(pct: number | null): SemaforoStatus {
  if (pct === null) return 'pendiente';
  return normSemaforo(pct);
}

/**
 * Los cinco números que hacen falta para explicar el cumplimiento de una norma
 * sin que nadie tenga que adivinar de dónde sale el porcentaje.
 *
 * Se devuelven juntos a propósito: el `pct` solo por sí mismo es engañoso —una
 * norma con un artículo en SI y diecinueve sin evaluar da 100 %— y separarlos
 * en cinco llamadas invita a que una pantalla muestre uno y se olvide del resto,
 * que es como se llegó al "No cumple 0 %".
 */
export function resumenDeNorma(norm: LegalNorm) {
  const total = norm.articulos.length;
  const aplicables = norm.articulos.filter((a) => a.respuesta !== 'NA').length;
  const evaluados = norm.articulos.filter(
    (a) => a.respuesta === 'SI' || a.respuesta === 'NO',
  ).length;
  return {
    pct: computeNormComplianceOrNull(norm),
    total,
    aplicables,
    evaluados,
    sinEvaluar: countArticulosSinEvaluar(norm),
    incumplidos: countArticulosEnIncumplimiento(norm),
  };
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
