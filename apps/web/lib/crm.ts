/**
 * El pipeline comercial, del lado del navegador (#81).
 *
 * Acá vive lo que se puede probar sin montar React: el mapeo desde la API, el
 * formato de plata y de fechas, y la única regla que la pantalla necesita
 * conocer por adelantado (perder exige motivo). Las reglas de verdad —cerrar,
 * reabrir, limpiar el cierre— viven en `services/crm.py` y no se repiten acá:
 * duplicarlas sería un segundo criterio que se desincroniza solo, que es
 * exactamente la lección que este repositorio ya aprendió con Zod y Pydantic.
 */

export type TipoDeEtapa = 'open' | 'won' | 'lost';

export interface EtapaCrm {
  id: string;
  codigo: string;
  nombre: string;
  posicion: number;
  tipo: TipoDeEtapa;
}

export interface TratoCrm {
  id: string;
  empresaId: string;
  contactoId: string | null;
  etapaId: string;
  titulo: string;
  /** `null` = **sin valorar**, que no es lo mismo que cero. */
  monto: number | null;
  moneda: string;
  responsableId: string | null;
  /** Fecha de calendario (`YYYY-MM-DD`), sin hora. Ver `formatearFecha`. */
  cierreEstimado: string | null;
  cerradoEn: string | null;
  motivoPerdida: string | null;
  contratoId: string | null;
}

export interface MontoPorMoneda {
  moneda: string;
  total: number;
}

export interface ColumnaPipeline {
  etapa: EtapaCrm;
  tratos: TratoCrm[];
  /** Cuántos hay **en total**, no cuántos se devolvieron. */
  totalTratos: number;
  /** Una entrada por moneda. Vacío = ningún trato de la columna tiene cifra. */
  montos: MontoPorMoneda[];
}

export interface Pipeline {
  columnas: ColumnaPipeline[];
  /** `true` = alguna columna se cortó en el tope del servidor. */
  truncado: boolean;
}

export const PIPELINE_VACIO: Pipeline = { columnas: [], truncado: false };

/** Los tipos de etapa que cierran el trato. */
export function esDeCierre(etapa: EtapaCrm): boolean {
  return etapa.tipo === 'won' || etapa.tipo === 'lost';
}

/**
 * Si mover a esta etapa va a exigir un motivo.
 *
 * La pantalla lo pregunta **antes** de mandar, no después de un 422: quien
 * arrastra una tarjeta a "Perdido" espera que le pidan la razón, no que le
 * rechacen el movimiento con un error de validación. El servidor lo exige
 * igual — esto es cortesía, no la barrera.
 */
export function necesitaMotivo(etapa: EtapaCrm): boolean {
  return etapa.tipo === 'lost';
}

// ── Formato ──────────────────────────────────────────────────────────────

const SOLO_FECHA = /^\d{4}-\d{2}-\d{2}$/;

const MESES = [
  'ene', 'feb', 'mar', 'abr', 'may', 'jun',
  'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
];

/**
 * Una fecha de calendario **sin pasarla por `Date`**.
 *
 * `expected_close_date` es un `date` de Postgres: un día, sin hora ni zona.
 * `new Date('2026-09-01')` lo interpreta como medianoche **UTC**, y en Chile
 * (UTC-3/-4) eso se muestra como el 31 de agosto. La fecha retrocede un día
 * sola, en silencio, y en una fecha de cierre eso mueve un trato de mes — y de
 * trimestre cuando cae en un límite.
 *
 * Ya pasó una vez en este repositorio con otra pantalla. Por eso se parte el
 * string en vez de construir una fecha.
 */
export function formatearFecha(valor: string | null): string {
  if (!valor) return 'Sin fecha';
  if (!SOLO_FECHA.test(valor)) {
    // No es una fecha de calendario: es una marca de tiempo, y esa sí se
    // convierte a la hora local a propósito.
    const d = new Date(valor);
    return Number.isNaN(d.getTime())
      ? 'Sin fecha'
      : d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
  }
  const [anio, mes, dia] = valor.split('-');
  const iMes = Number(mes) - 1;
  if (iMes < 0 || iMes > 11) return valor;
  return `${dia} ${MESES[iMes]} ${anio}`;
}

/**
 * Plata, con su moneda al lado y **nunca sin ella**.
 *
 * El símbolo `$` solo no distingue un peso de un dólar, y un pipeline de
 * "$ 1.000" que en realidad son dólares es un error de 900 mil pesos leído
 * como un dato normal.
 */
export function formatearMonto(total: number, moneda: string): string {
  const sinDecimales = moneda === 'CLP' || moneda === 'JPY';
  const numero = new Intl.NumberFormat('es-CL', {
    minimumFractionDigits: sinDecimales ? 0 : 2,
    maximumFractionDigits: sinDecimales ? 0 : 2,
  }).format(total);
  return `${moneda} ${numero}`;
}

/**
 * Lo que se muestra bajo el nombre de la columna.
 *
 * Con varias monedas se listan todas en vez de elegir una: elegir sería
 * esconder tratos, y sumarlas daría un número que no es plata de ninguna
 * clase. Sin ninguna, se dice "sin valorar" — no "0".
 */
export function resumenDeColumna(columna: ColumnaPipeline): string {
  if (columna.montos.length === 0) {
    return columna.totalTratos === 0 ? 'Sin oportunidades' : 'Sin valorar';
  }
  return columna.montos.map((m) => formatearMonto(m.total, m.moneda)).join(' · ');
}

// ── Mapeo desde la API ───────────────────────────────────────────────────

function texto(v: unknown): string {
  return v === null || v === undefined ? '' : String(v);
}

function textoONulo(v: unknown): string | null {
  return v === null || v === undefined || v === '' ? null : String(v);
}

/**
 * `amount` viaja como string en JSON (es un `numeric` de Postgres, y mandarlo
 * como número de JavaScript perdería precisión en montos grandes). Acá se
 * convierte a número **solo para mostrar**; ningún cálculo de negocio lo usa.
 */
function numeroONulo(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

const TIPOS: readonly string[] = ['open', 'won', 'lost'];

export function mapEtapa(raw: Record<string, unknown>): EtapaCrm {
  const tipo = texto(raw.kind);
  return {
    id: texto(raw.id),
    codigo: texto(raw.code),
    nombre: texto(raw.name),
    posicion: Number(raw.position ?? 0),
    // Un `kind` desconocido se trata como `open` y no se descarta la etapa: una
    // columna que desaparece del kanban se lleva sus tratos de la vista, y
    // parecen borrados.
    tipo: (TIPOS.includes(tipo) ? tipo : 'open') as TipoDeEtapa,
  };
}

export function mapTrato(raw: Record<string, unknown>): TratoCrm {
  return {
    id: texto(raw.id),
    empresaId: texto(raw.crm_company_id),
    contactoId: textoONulo(raw.crm_contact_id),
    etapaId: texto(raw.stage_id),
    titulo: texto(raw.title),
    monto: numeroONulo(raw.amount),
    moneda: texto(raw.currency) || 'CLP',
    responsableId: textoONulo(raw.owner_user_id),
    cierreEstimado: textoONulo(raw.expected_close_date),
    cerradoEn: textoONulo(raw.closed_at),
    motivoPerdida: textoONulo(raw.lost_reason),
    contratoId: textoONulo(raw.contract_id),
  };
}

export function mapPipeline(raw: Record<string, unknown>): Pipeline {
  const columnas = Array.isArray(raw.columnas) ? raw.columnas : [];
  return {
    columnas: columnas.map((c) => {
      const col = c as Record<string, unknown>;
      const tratos = Array.isArray(col.deals) ? col.deals : [];
      const montos = Array.isArray(col.montos) ? col.montos : [];
      return {
        etapa: mapEtapa((col.stage ?? {}) as Record<string, unknown>),
        tratos: tratos.map((d) => mapTrato(d as Record<string, unknown>)),
        // **Del servidor, no de `tratos.length`.** La lista puede venir cortada
        // en el tope, y contar lo visible daría un total menor que el real sin
        // que nada lo diga.
        totalTratos: Number(col.total_deals ?? 0),
        montos: montos
          .map((m) => {
            const mm = m as Record<string, unknown>;
            return { moneda: texto(mm.moneda) || 'CLP', total: Number(mm.total ?? 0) };
          })
          .filter((m) => Number.isFinite(m.total)),
      };
    }),
    truncado: raw.truncado === true,
  };
}
