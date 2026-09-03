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

/* ─────────────────────────────────────────────────────────────────────────
 * Empresas, contactos y actividades
 *
 * La API del CRM tiene 28 operaciones y la interfaz llamaba a **dos**, desde
 * una sola pantalla: el pipeline. Se podía mirar el tablero y arrastrar un
 * trato, y nada más — no crear una empresa, ni registrar una llamada, ni
 * promover un trato ganado.
 *
 * Lo de abajo es lo que faltaba para que el módulo se pueda usar, con el mismo
 * criterio del resto del archivo: mapear la respuesta y **no repetir reglas de
 * negocio** que ya viven en `services/crm.py`.
 * ───────────────────────────────────────────────────────────────────────── */

/** Prospecto, cliente o inactiva. Los tres valores que admite la base. */
export type EstadoDeEmpresa = 'prospect' | 'client' | 'inactive';

export interface EmpresaCrm {
  id: string;
  nombre: string;
  rut: string | null;
  rubro: string | null;
  sitioWeb: string | null;
  /**
   * La empresa **dentro de la plataforma**, cuando ya es cliente.
   *
   * `null` mientras es prospecto. Es el puente que permite promover un trato
   * ganado a contrato: sin él no hay a quién asociarle el contrato.
   */
  clienteTenantId: string | null;
  estado: EstadoDeEmpresa;
  responsableId: string | null;
  notas: string | null;
}

export interface ContactoCrm {
  id: string;
  empresaId: string;
  nombre: string;
  correo: string | null;
  telefono: string | null;
  cargo: string | null;
  /** El interlocutor por defecto de esa empresa. */
  esPrincipal: boolean;
}

/** Los cinco tipos que admite la base. */
export type TipoDeActividad = 'call' | 'email' | 'meeting' | 'note' | 'task';

export interface ActividadCrm {
  id: string;
  tipo: TipoDeActividad;
  asunto: string;
  detalle: string | null;
  ocurrioEn: string;
  autorId: string | null;
  empresaId: string | null;
  contactoId: string | null;
  tratoId: string | null;
}

export const ESTADO_DE_EMPRESA: Record<EstadoDeEmpresa, string> = {
  prospect: 'Prospecto',
  client: 'Cliente',
  inactive: 'Inactiva',
};

export const TIPO_DE_ACTIVIDAD: Record<TipoDeActividad, string> = {
  call: 'Llamada',
  email: 'Correo',
  meeting: 'Reunión',
  note: 'Nota',
  task: 'Tarea',
};

export function mapEmpresa(raw: Record<string, unknown>): EmpresaCrm {
  return {
    id: String(raw.id),
    nombre: String(raw.name ?? ''),
    rut: raw.rut ? String(raw.rut) : null,
    rubro: raw.industry ? String(raw.industry) : null,
    sitioWeb: raw.website ? String(raw.website) : null,
    clienteTenantId: raw.client_tenant_id ? String(raw.client_tenant_id) : null,
    estado: (String(raw.status ?? 'prospect') as EstadoDeEmpresa),
    responsableId: raw.owner_user_id ? String(raw.owner_user_id) : null,
    notas: raw.notes ? String(raw.notes) : null,
  };
}

export function mapContacto(raw: Record<string, unknown>): ContactoCrm {
  return {
    id: String(raw.id),
    empresaId: String(raw.crm_company_id),
    nombre: String(raw.full_name ?? ''),
    correo: raw.email ? String(raw.email) : null,
    telefono: raw.phone ? String(raw.phone) : null,
    cargo: raw.role_title ? String(raw.role_title) : null,
    esPrincipal: Boolean(raw.is_primary),
  };
}

export function mapActividad(raw: Record<string, unknown>): ActividadCrm {
  return {
    id: String(raw.id),
    tipo: (String(raw.kind ?? 'note') as TipoDeActividad),
    asunto: String(raw.subject ?? ''),
    detalle: raw.body ? String(raw.body) : null,
    ocurrioEn: String(raw.occurred_at ?? raw.created_at ?? ''),
    autorId: raw.author_user_id ? String(raw.author_user_id) : null,
    empresaId: raw.crm_company_id ? String(raw.crm_company_id) : null,
    contactoId: raw.crm_contact_id ? String(raw.crm_contact_id) : null,
    tratoId: raw.crm_deal_id ? String(raw.crm_deal_id) : null,
  };
}

export interface ContratoParaPromover {
  id: string;
  numero: string;
  titulo: string;
  clienteTenantId: string;
  estado: string;
}

export function mapContratoParaPromover(
  raw: Record<string, unknown>,
): ContratoParaPromover {
  return {
    id: String(raw.id),
    numero: String(raw.contract_number ?? ''),
    titulo: String(raw.title ?? ''),
    clienteTenantId: String(raw.client_tenant_id ?? ''),
    estado: String(raw.status ?? ''),
  };
}

/**
 * Si el trato se puede promover a contrato.
 *
 * ## La condición es la etapa, y esto estuvo mal escrito
 *
 * La primera versión exigía que la empresa **ya tuviera** `client_tenant_id`, y
 * era exactamente al revés: promover es lo que lo **fija**
 * (`services/crm.py::promover_a_contrato`). Con esa condición el botón se
 * escondía justo en el caso para el que existe — un prospecto al que se le
 * acaba de ganar el trato — y aparecía solo en las fichas donde ya no hacía
 * falta.
 *
 * Lo que el servidor exige de verdad son dos cosas: que el trato esté en una
 * etapa de tipo `won`, y que no apunte ya a otro contrato.
 */
export function sePuedePromover(trato: TratoCrm, etapa: EtapaCrm | null): boolean {
  return etapa?.tipo === 'won' && !trato.contratoId;
}

/** Por qué no se puede promover, en palabras. `null` si sí se puede. */
export function motivoParaNoPromover(
  trato: TratoCrm,
  etapa: EtapaCrm | null,
): string | null {
  if (trato.contratoId) {
    return (
      'Este trato ya está enlazado a un contrato. Mover el enlace dejaría al ' +
      'contrato anterior sin la venta que lo originó.'
    );
  }
  if (etapa === null) return 'No se sabe en qué etapa está el trato.';
  if (etapa.tipo !== 'won') {
    return `Solo un trato ganado se promueve a contrato. Este está en «${etapa.nombre}».`;
  }
  return null;
}

/**
 * Los contratos que el servidor va a aceptar para esta ficha.
 *
 * Si la empresa ya nombra a un cliente de la plataforma, un contrato de otro
 * cliente se rechaza con 409 (`ClienteDistinto`). Filtrarlos acá evita ofrecer
 * en el selector opciones que van a fallar; **la barrera sigue siendo el
 * servidor**, esto es cortesía.
 */
export function contratosCompatibles(
  empresa: EmpresaCrm,
  contratos: ContratoParaPromover[],
): ContratoParaPromover[] {
  if (!empresa.clienteTenantId) return contratos;
  return contratos.filter((c) => c.clienteTenantId === empresa.clienteTenantId);
}

/* ─────────────────────────────────────────────────────────────────────────
 * Configuración del pipeline y responsables
 * ───────────────────────────────────────────────────────────────────────── */

/** Qué significa cada tipo de etapa para quien configura el pipeline. */
export const TIPO_DE_ETAPA: Record<TipoDeEtapa, string> = {
  open: 'Abierta',
  won: 'Ganado',
  lost: 'Perdido',
};

export const AYUDA_DEL_TIPO: Record<TipoDeEtapa, string> = {
  open: 'El trato sigue vivo. Los nuevos entran en la primera de estas.',
  won: 'Al llegar acá el trato se cierra, y desde acá se promueve a contrato.',
  lost: 'Al llegar acá el trato se cierra y se exige el motivo de la pérdida.',
};

/**
 * Una persona de la empresa, para asignarle una ficha o un trato.
 *
 * **Sale de `/users/`, no de `useUsers()`.** Ese store arranca con `mockUsers` y
 * se queda con ellos si la API falla, así que un selector construido sobre él
 * ofrecería identificadores que no existen en la base — y `owner_user_id` es
 * una clave foránea: la escritura respondería 422. Ya pasó en este repositorio
 * con el selector de plantas.
 */
export interface PersonaAsignable {
  id: string;
  nombre: string;
}

export function mapPersona(raw: Record<string, unknown>): PersonaAsignable {
  return {
    id: String(raw.id),
    nombre: String(raw.full_name ?? raw.email ?? 'Sin nombre'),
  };
}

/** El nombre de quien está a cargo, o el aviso de que no hay nadie. */
export function nombreDelResponsable(
  responsableId: string | null,
  personas: PersonaAsignable[],
): string {
  if (!responsableId) return 'Sin responsable';
  // Un id que no está en la lista **se dice**, no se esconde tras «Sin
  // responsable»: son cosas distintas — alguien está a cargo y no sabemos
  // quién, contra nadie está a cargo. La segunda es la que hay que repartir.
  return personas.find((p) => p.id === responsableId)?.nombre ?? 'Responsable desconocido';
}

/**
 * Si retirar esta etapa va a ser rechazado, y por qué.
 *
 * Las mismas dos reglas que `services/crm.py::comprobar_cambio_de_etapa`, con
 * una diferencia que importa: **acá no son la barrera**. El servidor responde
 * 409 igual. Existen para no ofrecer un botón que va a fallar, y para explicar
 * la salida antes de que alguien la busque probando.
 */
export function motivoParaNoRetirarEtapa(
  etapa: EtapaCrm,
  todas: EtapaCrm[],
  tratosEnLaEtapa: number,
): string | null {
  if (tratosEnLaEtapa > 0) {
    return (
      `Tiene ${tratosEnLaEtapa} oportunidad${tratosEnLaEtapa === 1 ? '' : 'es'} dentro. ` +
      'Retirarla las dejaría fuera del tablero sin borrarlas. Muévelas primero.'
    );
  }
  const otrasDeSuTipo = todas.filter((e) => e.tipo === etapa.tipo && e.id !== etapa.id);
  if (otrasDeSuTipo.length === 0) {
    return (
      `Es la única etapa «${TIPO_DE_ETAPA[etapa.tipo]}» que queda, y el pipeline ` +
      'la necesita. Se puede renombrar y reordenar.'
    );
  }
  return null;
}

/**
 * El `code` de una etapa nueva, derivado de su nombre.
 *
 * ## Por qué no se pide
 *
 * `code` es el identificador estable de la columna y **no se puede cambiar
 * después**. Pedirlo aparte sería pedir un dato técnico a quien está
 * describiendo su proceso de venta, y quien lo escriba mal se queda con él.
 *
 * ## Y por qué recibe los que ya existen
 *
 * Hay un índice único por `(tenant_id, code)`. Dos etapas llamadas «Propuesta»
 * y «propuesta!» dan el mismo código y la segunda respondería 409, con un
 * mensaje sobre una columna que la persona no sabe que existe. Se numera.
 *
 * Devuelve cadena vacía si del nombre no queda nada utilizable —un nombre hecho
 * solo de símbolos—, y ahí la pantalla no deja guardar: es preferible a mandar
 * un código vacío que la base rechaza por otra razón.
 */
export function codigoDeEtapa(nombre: string, yaUsados: string[] = []): string {
  const base = nombre
    .trim()
    .toLowerCase()
    .normalize('NFD')
    // Los diacríticos combinantes que `NFD` separó. Se quitan en vez de
    // traducirse: `ñ` → `n` es lo que se espera de un identificador.
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40);

  if (!base) return '';
  if (!yaUsados.includes(base)) return base;

  for (let n = 2; n < 100; n += 1) {
    const candidato = `${base.slice(0, 37)}_${n}`;
    if (!yaUsados.includes(candidato)) return candidato;
  }
  return '';
}
