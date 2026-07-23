import type { Articulo, LegalNorm } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms';

/**
 * % de cumplimiento de una norma = SI / (SI + NO) entre los artículos marcados
 * `incluidoEnCalculo` (RF-13, S-11) — NA y N_E (pendiente de evaluar) no cuentan
 * en el denominador. Réplica en el frontend de la vista SQL
 * `resumen_cumplimiento_requisito` documentada en el ADD (docs/arquitectura).
 */
export function computeNormCompliance(norm: LegalNorm): number {
  const evaluables = norm.articulos.filter((a) => a.incluidoEnCalculo && (a.respuesta === 'SI' || a.respuesta === 'NO'));
  if (evaluables.length === 0) return 0;
  const cumplidos = evaluables.filter((a) => a.respuesta === 'SI').length;
  return cumplidos / evaluables.length;
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
