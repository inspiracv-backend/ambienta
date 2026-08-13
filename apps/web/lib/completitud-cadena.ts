import type { AspectoAmbiental, LegalNorm } from '@ambienta/shared';
import { aspectoSinTratar } from '@ambienta/shared';

/**
 * Qué tan completa está la cadena de ISO 14001, no qué tan bien se cumple.
 *
 * ```
 * AspectoAmbiental (§6.1.2) ──┬──► RiesgoOportunidad (§6.1.4)
 *                             └──► LegalNorm (§6.1.3)
 * ```
 *
 * Cada flecha responde un "¿por qué?". El design lo dice en una línea que vale
 * la pena repetir: **un requisito sin aspecto es un requisito que nadie
 * justificó; un aspecto significativo sin riesgo ni requisito es un aspecto que
 * nadie trató.**
 *
 * Esto es un tercer indicador, distinto de los dos que ya existen:
 *
 * | Indicador | Responde |
 * |---|---|
 * | Cumplimiento | ¿cumplimos lo que evaluamos? |
 * | Cobertura | ¿cuánto alcanzamos a evaluar? |
 * | **Completitud** | ¿está armada la cadena que justifica lo que evaluamos? |
 *
 * Los tres pueden verse bien por separado y tapar el mismo problema: una
 * empresa puede tener 100 % de cumplimiento sobre 100 % de cobertura de una
 * lista de requisitos que **nadie derivó de sus aspectos ambientales**. Eso es
 * exactamente el hallazgo de auditoría que ISO busca, y ningún indicador de
 * cumplimiento lo ve.
 */
export interface CompletitudCadena {
  /** Aspectos marcados como significativos. El denominador que importa. */
  aspectosSignificativos: number;
  /** Significativos sin ningún requisito ni riesgo asociado. */
  aspectosSinTratar: number;
  /** Requisitos legales considerados. */
  requisitos: number;
  /** Requisitos que ningún aspecto justifica. */
  requisitosSinAspecto: number;
  /**
   * Enlaces que apuntan a algo que no está en el conjunto recibido.
   *
   * No entra en la razón: es una **inconsistencia de datos**, no una tarea
   * pendiente, y mezclarlas haría que arreglar un id roto se leyera como
   * avance de gestión ambiental. Se cuenta aparte porque, si nadie lo mira, un
   * enlace roto se ve igual que un enlace correcto.
   */
  enlacesRotos: number;
  /** Enlaces resueltos sobre enlaces esperados, entre 0 y 1. */
  completitud: number;
}

/**
 * Un aspecto **no significativo** sin tratamiento no cuenta como hueco: decidir
 * que algo no es significativo es justamente la decisión de no tratarlo. Meterlo
 * en el denominador castigaría a quien evaluó bien.
 *
 * Sin nada que evaluar devuelve 1, igual que `computeNormCoverage` con cero
 * artículos aplicables: la ausencia de datos no es un incumplimiento.
 */
export function calcularCompletitudCadena(
  aspectos: AspectoAmbiental[],
  normas: LegalNorm[],
): CompletitudCadena {
  const significativos = aspectos.filter((a) => a.significativo);
  const sinTratar = significativos.filter(aspectoSinTratar);

  // `aplicabilidad` entera es opcional, y una norma sin ella no es un caso
  // aparte: es el mismo hueco en su forma más pura. Nadie escribió por qué esa
  // norma le aplica a esta empresa.
  const aspectosDe = (n: LegalNorm) => n.aplicabilidad?.aspectoAmbientalIds ?? [];

  const sinAspecto = normas.filter((n) => aspectosDe(n).length === 0);

  const idsAspecto = new Set(aspectos.map((a) => a.id));
  const idsNorma = new Set(normas.map((n) => n.id));

  let enlacesRotos = 0;
  for (const aspecto of aspectos) {
    for (const id of aspecto.requisitoLegalIds) {
      if (!idsNorma.has(id)) enlacesRotos += 1;
    }
  }
  for (const norma of normas) {
    for (const id of aspectosDe(norma)) {
      if (!idsAspecto.has(id)) enlacesRotos += 1;
    }
  }

  const esperados = significativos.length + normas.length;
  const resueltos = significativos.length - sinTratar.length + (normas.length - sinAspecto.length);

  return {
    aspectosSignificativos: significativos.length,
    aspectosSinTratar: sinTratar.length,
    requisitos: normas.length,
    requisitosSinAspecto: sinAspecto.length,
    enlacesRotos,
    completitud: esperados === 0 ? 1 : resueltos / esperados,
  };
}
