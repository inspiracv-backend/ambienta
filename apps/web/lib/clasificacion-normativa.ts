import { api } from '@/lib/api-client';

/**
 * Cuánta normativa falta clasificar, y dónde.
 *
 * ## Por qué esta pantalla existe
 *
 * Todo el mecanismo de normativa aplicable descansa en `norm_sectors`: una
 * norma sin clasificar no le llega a ninguna empresa. La tabla nace vacía, así
 * que el sistema **funciona entero y no propone nada** — y la única señal es
 * que la matriz responde "sector sin clasificar", que se lee como una falla
 * técnica cuando en realidad es trabajo pendiente de una persona.
 *
 * Esto lo convierte en un número visible. No arregla el vacío; lo hace
 * imposible de ignorar.
 */

export interface CoberturaDeSector {
  sectorId: number;
  codigo: string;
  nombre: string;
  /** Obligatorias para el sector (`directa`). */
  directas: number;
  /** `indirecta` + `referencial`: se proponen, no obligan. */
  recomendadas: number;
  total: number;
}

export interface Cobertura {
  normasTotales: number;
  /** Normas sin **ninguna** clasificación. El trabajo pendiente. */
  normasSinClasificar: number;
  /** Sectores donde una empresa entraría y no recibiría nada. */
  sectoresSinNormativa: number;
  porSector: CoberturaDeSector[];
}

/** Lo que se muestra mientras no hay datos: ceros honestos, no una pantalla vacía. */
export const COBERTURA_VACIA: Cobertura = {
  normasTotales: 0,
  normasSinClasificar: 0,
  sectoresSinNormativa: 0,
  porSector: [],
};

function mapearSector(raw: Record<string, unknown>): CoberturaDeSector {
  return {
    sectorId: Number(raw.sector_id),
    codigo: String(raw.codigo ?? ''),
    nombre: String(raw.nombre ?? ''),
    directas: Number(raw.directas ?? 0),
    recomendadas: Number(raw.recomendadas ?? 0),
    total: Number(raw.total ?? 0),
  };
}

export function mapearCobertura(raw: unknown): Cobertura {
  if (!raw || typeof raw !== 'object') return COBERTURA_VACIA;
  const o = raw as Record<string, unknown>;
  return {
    normasTotales: Number(o.normas_totales ?? 0),
    normasSinClasificar: Number(o.normas_sin_clasificar ?? 0),
    sectoresSinNormativa: Number(o.sectores_sin_normativa ?? 0),
    porSector: Array.isArray(o.por_sector)
      ? (o.por_sector as Record<string, unknown>[]).map(mapearSector)
      : [],
  };
}

export function cargarCobertura(): Promise<Cobertura> {
  return api
    .get<Record<string, unknown>>('/catalog/clasificacion/cobertura')
    .then(mapearCobertura);
}

/**
 * Qué tan urgente es este sector.
 *
 * **`sin-normativa` no es "va bien porque no hay nada rojo".** Un sector en
 * cero es el peor caso: una empresa de ese rubro entra al sistema, completa su
 * perfil y no recibe ninguna obligación. Se ve peor que uno a medias porque
 * lo es.
 */
export type Urgencia = 'sin-normativa' | 'solo-recomendadas' | 'con-obligatorias';

export function urgenciaDe(sector: CoberturaDeSector): Urgencia {
  if (sector.total === 0) return 'sin-normativa';
  if (sector.directas === 0) return 'solo-recomendadas';
  return 'con-obligatorias';
}

export const ETIQUETA_DE_URGENCIA: Record<Urgencia, string> = {
  'sin-normativa': 'Sin normativa',
  'solo-recomendadas': 'Solo recomendadas',
  'con-obligatorias': 'Con obligatorias',
};

/**
 * El porcentaje clasificado, o `null` si no hay normas.
 *
 * `null`, no cero: sin catálogo cargado no es que nadie haya clasificado, es
 * que todavía no hay nada que clasificar. Es la misma distinción que hace el
 * porcentaje de cumplimiento.
 */
export function porcentajeClasificado(c: Cobertura): number | null {
  if (c.normasTotales === 0) return null;
  return Math.round(((c.normasTotales - c.normasSinClasificar) / c.normasTotales) * 100);
}
