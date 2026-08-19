import { api } from '@/lib/api-client';

/**
 * La normativa que le corresponde a la empresa, antes de generar la matriz.
 *
 * ## Por qué es un check y no un botón que genera
 *
 * Calcular y aplicar son operaciones distintas a propósito. El negocio pidió
 * "un check de normativas recomendadas", y un check es una revisión humana
 * antes de comprometerse: generar de golpe le daría a la empresa cientos de
 * artículos que evaluar sin que nadie mirara si tienen sentido.
 */

/**
 * Por qué la lista puede venir vacía.
 *
 * **Los tres estados se ven igual en pantalla si solo se muestra la lista**, y
 * el más peligroso —`sector_sin_clasificar`— se lee como estar en regla. Ni
 * `sin_perfil` ni `sector_sin_clasificar` significan que la empresa no tenga
 * obligaciones: significan que todavía no se sabe cuáles son.
 */
export type EstadoNormativa = 'sin_perfil' | 'sector_sin_clasificar' | 'con_normativa';

export interface NormaAplicable {
  normId: string;
  titulo: string;
  tipo: string;
  numero: string | null;
  sectorId: number;
  /** `directa` = obligatoria. `indirecta` y `referencial` = recomendada. */
  nivel: string;
  /** Por qué entró. Es la respuesta a "cómo determinaron que esto les aplica". */
  motivo: string | null;
}

export interface NormativaAplicable {
  estado: EstadoNormativa;
  sectorId: number | null;
  obligatorias: NormaAplicable[];
  recomendadas: NormaAplicable[];
  total: number;
}

export const NORMATIVA_VACIA: NormativaAplicable = {
  estado: 'sin_perfil',
  sectorId: null,
  obligatorias: [],
  recomendadas: [],
  total: 0,
};

const ESTADOS: readonly string[] = ['sin_perfil', 'sector_sin_clasificar', 'con_normativa'];

function mapearNorma(raw: Record<string, unknown>): NormaAplicable {
  return {
    normId: String(raw.norm_id ?? ''),
    titulo: String(raw.title ?? ''),
    tipo: String(raw.norm_type ?? ''),
    numero: raw.norm_number == null ? null : String(raw.norm_number),
    sectorId: Number(raw.sector_id ?? 0),
    nivel: String(raw.applicability_level ?? ''),
    motivo: raw.rationale == null ? null : String(raw.rationale),
  };
}

function lista(valor: unknown): NormaAplicable[] {
  return Array.isArray(valor) ? (valor as Record<string, unknown>[]).map(mapearNorma) : [];
}

export function mapearNormativa(raw: unknown): NormativaAplicable {
  if (!raw || typeof raw !== 'object') return NORMATIVA_VACIA;
  const o = raw as Record<string, unknown>;
  return {
    // Un estado que no reconocemos cae en `sin_perfil`, el más conservador de
    // los tres: dice "falta un dato", no "no hay obligaciones".
    estado: ESTADOS.includes(String(o.estado))
      ? (o.estado as EstadoNormativa)
      : 'sin_perfil',
    sectorId: o.sector_id == null ? null : Number(o.sector_id),
    obligatorias: lista(o.obligatorias),
    recomendadas: lista(o.recomendadas),
    total: Number(o.total ?? 0),
  };
}

export function cargarNormativaAplicable(tenantId: string): Promise<NormativaAplicable> {
  return api
    .get<Record<string, unknown>>('/compliance/normativa-aplicable', { tenantId })
    .then(mapearNormativa);
}

/**
 * Qué decirle a la persona cuando no hay nada que mostrar.
 *
 * Los tres mensajes son distintos porque **la acción que corresponde es
 * distinta**, y quién la tiene que hacer también: en un caso es la empresa, en
 * el otro somos nosotros. Un "no hay normativa aplicable" genérico dejaría a la
 * empresa creyendo que está en regla.
 */
export const EXPLICACION_DEL_ESTADO: Record<
  EstadoNormativa,
  { titulo: string; detalle: string } | null
> = {
  sin_perfil: {
    titulo: 'Falta declarar el sector de la empresa',
    detalle:
      'Sin sector económico no se puede determinar qué normativa le aplica. Se declara en el perfil de la empresa.',
  },
  sector_sin_clasificar: {
    titulo: 'Todavía no hay normas clasificadas para este sector',
    detalle:
      'Esto no significa que la empresa no tenga obligaciones: significa que aún no las hemos clasificado. Está pendiente de nuestro lado.',
  },
  con_normativa: null,
};

/** `directa` obliga; los otros dos niveles se proponen. */
export function esObligatoria(nivel: string): boolean {
  return nivel === 'directa';
}

export const ETIQUETA_DE_NIVEL: Record<string, string> = {
  directa: 'Aplicación directa',
  indirecta: 'Aplicación indirecta',
  referencial: 'Referencial',
};

// ── Normas desactualizadas (7.4) ───────────────────────────────────────────

/**
 * Una norma de la matriz evaluada contra una versión que ya no rige.
 *
 * `evaluacionesSobreLaAnterior` **no es trabajo perdido**: esas evaluaciones se
 * hicieron sobre el texto que regía entonces, y esa es la respuesta correcta
 * ante una auditoría de ese período. El número dimensiona el esfuerzo de
 * revisar, no alarma.
 */
export interface NormaDesactualizada {
  matrixNormId: string;
  normId: string;
  titulo: string;
  versionEvaluada: string;
  versionVigente: string;
  evaluacionesSobreLaAnterior: number;
}

export function mapearDesactualizada(raw: Record<string, unknown>): NormaDesactualizada {
  return {
    matrixNormId: String(raw.matrix_norm_id ?? ''),
    normId: String(raw.norm_id ?? ''),
    titulo: String(raw.title ?? ''),
    versionEvaluada: String(raw.version_evaluada ?? ''),
    versionVigente: String(raw.version_vigente ?? ''),
    evaluacionesSobreLaAnterior: Number(raw.evaluaciones_sobre_la_anterior ?? 0),
  };
}

export function cargarDesactualizadas(
  matrixId: string,
  tenantId: string,
): Promise<NormaDesactualizada[]> {
  return api
    .get<Record<string, unknown>[]>(`/compliance/matrices/${matrixId}/desactualizadas`, {
      tenantId,
    })
    .then((filas) => (Array.isArray(filas) ? filas.map(mapearDesactualizada) : []));
}

/**
 * La matriz vigente de la empresa: la del período más reciente.
 *
 * Devuelve `null` cuando no hay ninguna, y eso es un estado normal —una empresa
 * recién creada todavía no generó su matriz—, no un error que haya que
 * reportar.
 */
export function matrizMasReciente(filas: unknown): string | null {
  if (!Array.isArray(filas) || filas.length === 0) return null;
  // Se ordena por período y **no se toma la primera**: el orden que devuelve la
  // API no está garantizado, y avisar sobre la matriz del año pasado mientras
  // se mira la de este sería peor que no avisar.
  const ordenadas = [...(filas as Record<string, unknown>[])].sort(
    (a, b) => Number(b.period_year ?? 0) - Number(a.period_year ?? 0),
  );
  return String(ordenadas[0]!.id ?? '') || null;
}

export function cargarMatrizVigente(tenantId: string): Promise<string | null> {
  return api
    .get<Record<string, unknown>[]>('/compliance/matrices', { tenantId })
    .then(matrizMasReciente)
    .catch(() => null);
}
