import { api } from '@/lib/api-client';

/**
 * Lo que la empresa está incumpliendo ahora mismo (#126, RF-56).
 *
 * El detalle detrás del número del tablero: `/dashboard/metrics` dice
 * **cuánto**, esto dice **qué**, y con qué se respalda.
 *
 * ## Por qué es un módulo y no un store con provider
 *
 * Los stores con contexto existen para datos que **varias pantallas comparten y
 * mutan** — obligaciones, matriz legal, usuarios. Esto es una lectura de una
 * sola pantalla que nadie edita: montar un provider sería agregar un nodo al
 * árbol de toda la aplicación para un dato que solo se usa en un sitio.
 */

/** Un requisito legal que la empresa reconoce que no cumple. */
export interface ArticuloEnIncumplimiento {
  articleComplianceId: string;
  normaTitulo: string;
  normaNumero: string;
  articuloNumero: string;
  articuloEpigrafe: string | null;
  /** `null` = evaluado a nivel de empresa, sin planta concreta. */
  planta: string | null;
  /**
   * El enlace a la evidencia.
   *
   * **`null` es el caso que importa.** Un incumplimiento documentado tiene algo
   * que mostrar; uno sin evidencia deja a la empresa muda cuando llega una
   * fiscalización.
   */
  evidenciaUrl: string | null;
  formaCumplimiento: string | null;
  riesgo: string | null;
}

/** Un trámite que no se presentó a tiempo. */
export interface DeclaracionVencida {
  obligationId: string;
  codigo: string;
  titulo: string;
  venceEl: string | null;
  estado: string;
  folio: string | null;
  planta: string | null;
  diasVencida: number | null;
}

export interface Incumplimientos {
  articulos: ArticuloEnIncumplimiento[];
  declaraciones: DeclaracionVencida[];
  /** La lista se cortó en el tope del servidor. **Se dice, no se oculta.** */
  articulosTruncados: boolean;
  declaracionesTruncadas: boolean;
  /** Cuántos de los artículos listados no tienen evidencia. */
  articulosSinEvidencia: number;
}

/** El vacío que corresponde antes de que la API responda. */
export const VACIO: Incumplimientos = {
  articulos: [],
  declaraciones: [],
  articulosTruncados: false,
  declaracionesTruncadas: false,
  articulosSinEvidencia: 0,
};

/**
 * Trae los incumplimientos y traduce el contrato de la API.
 *
 * La conversión vive acá y no en el componente por la misma razón de siempre en
 * este repo: dos vocabularios que se cruzan —`snake_case` y `camelCase`— y un
 * error en el cruce **no rompe nada**, solo deja campos vacíos que se leen como
 * "no hay datos".
 */
export async function cargarIncumplimientos(tenantId: string): Promise<Incumplimientos> {
  const d = await api.get<Record<string, unknown>>('/dashboard/incumplimientos', {
    tenantId,
  });

  const articulos = (d.articles ?? []) as Record<string, unknown>[];
  const declaraciones = (d.declarations ?? []) as Record<string, unknown>[];

  return {
    articulos: articulos.map((a) => ({
      articleComplianceId: String(a.article_compliance_id),
      normaTitulo: String(a.norm_title ?? ''),
      normaNumero: String(a.norm_number ?? ''),
      articuloNumero: String(a.article_number ?? ''),
      articuloEpigrafe: a.article_heading ? String(a.article_heading) : null,
      planta: a.facility_name ? String(a.facility_name) : null,
      evidenciaUrl: a.evidence_url ? String(a.evidence_url) : null,
      formaCumplimiento: a.compliance_method ? String(a.compliance_method) : null,
      riesgo: a.risk_level ? String(a.risk_level) : null,
    })),
    declaraciones: declaraciones.map((x) => ({
      obligationId: String(x.obligation_id),
      codigo: String(x.code ?? ''),
      titulo: String(x.title ?? ''),
      venceEl: x.due_at ? String(x.due_at) : null,
      estado: String(x.status ?? ''),
      folio: x.external_receipt ? String(x.external_receipt) : null,
      planta: x.facility_name ? String(x.facility_name) : null,
      diasVencida: typeof x.days_overdue === 'number' ? x.days_overdue : null,
    })),
    articulosTruncados: Boolean(d.articles_truncated),
    declaracionesTruncadas: Boolean(d.declarations_truncated),
    // `Number(...)` y no `?? 0`: si la API dejara de mandarlo, un `0` silencioso
    // diría "todos tienen evidencia", que es la lectura tranquilizadora falsa.
    articulosSinEvidencia: Number(d.articles_without_evidence ?? 0),
  };
}
