import { api } from '@/lib/api-client';

/**
 * El ciclo de una auditoría contra la API real: crearla, cargar su checklist,
 * responderlo y llevarla hasta el cierre.
 *
 * ## Por qué no pasa por `audits-store`
 *
 * El modelo compartido (`Audit`) tiene tres estados y ningún código ni título:
 * sirve para listar, no para operar. Aquí se trabaja con el **vocabulario de la
 * base** —`planned | active | reporting | closed | cancelled`— porque es el que
 * decide qué transición se puede pedir. Traducirlo a tres estados escondería
 * justo la diferencia entre "en ejecución" y "en informe".
 *
 * Hasta el 19-sep la API tenía todo esto y **ninguna pantalla lo llamaba**: no
 * se podía crear una auditoría, cargarle preguntas ni cerrarla, y sin preguntas
 * no se podía registrar un hallazgo con origen en una auditoría.
 */

export type EstadoAuditoria = 'planned' | 'active' | 'reporting' | 'closed' | 'cancelled';
export type ResultadoPregunta = 'pending' | 'conform' | 'nonconform' | 'observation' | 'not_applicable';
export type TipoAuditoria = 'internal' | 'external' | 'regulatory' | 'supplier';

export const ESTADO_AUDITORIA_LABEL: Record<EstadoAuditoria, string> = {
  planned: 'Planificada',
  active: 'En ejecución',
  reporting: 'En informe',
  closed: 'Cerrada',
  cancelled: 'Cancelada',
};

export const TIPO_AUDITORIA_LABEL: Record<TipoAuditoria, string> = {
  internal: 'Interna',
  external: 'Externa (certificación)',
  regulatory: 'Fiscalización',
  supplier: 'A un proveedor',
};

export const RESULTADO_LABEL: Record<ResultadoPregunta, string> = {
  pending: 'Sin responder',
  conform: 'Conforme',
  nonconform: 'No conforme',
  observation: 'Observación',
  not_applicable: 'No aplica',
};

/**
 * Las transiciones que acepta `POST /audits/{id}/advance`.
 *
 * **Espejo de `AUDIT_STATUS_TRANSITIONS`** en `apps/api/app/services/audits.py`;
 * `ciclo-de-auditoria.test.ts` lee ese archivo y exige que coincidan. Ofrecer
 * un botón que la API rechaza es peor que no ofrecerlo: se lee como un fallo.
 */
export const TRANSICIONES: Record<EstadoAuditoria, { a: EstadoAuditoria; accion: string }[]> = {
  planned: [
    { a: 'active', accion: 'Iniciar la auditoría' },
    { a: 'cancelled', accion: 'Cancelar' },
  ],
  active: [
    { a: 'reporting', accion: 'Pasar a informe' },
    { a: 'cancelled', accion: 'Cancelar' },
  ],
  reporting: [
    { a: 'closed', accion: 'Cerrar la auditoría' },
    { a: 'cancelled', accion: 'Cancelar' },
  ],
  closed: [],
  cancelled: [],
};

/** Cerrada o cancelada: la API responde 409 a cualquier cambio del checklist. */
export function checklistAbierto(estado: EstadoAuditoria): boolean {
  return estado !== 'closed' && estado !== 'cancelled';
}

export interface Auditoria {
  id: string;
  codigo: string;
  titulo: string;
  tipo: string;
  alcance: string;
  plantaId: string | null;
  estado: EstadoAuditoria;
  inicioPlanificado: string | null;
  finPlanificado: string | null;
  inicioReal: string | null;
  finReal: string | null;
}

export interface Pregunta {
  id: string;
  secuencia: number;
  pregunta: string;
  resultado: ResultadoPregunta;
  notas: string;
  procesoId: string | null;
  articuloEvaluadoId: string | null;
  respondidaEl: string | null;
}

export interface Cobertura {
  aplicables: number;
  cubiertos: number;
  /** `null` cuando no hay nada aplicable: no es un 0 %. */
  porcentaje: number | null;
  preguntasSinArticulo: number;
}

const texto = (v: unknown): string | null => (v === null || v === undefined || v === '' ? null : String(v));

export function auditoriaDesdeApi(raw: Record<string, unknown>): Auditoria {
  return {
    id: String(raw.id),
    codigo: String(raw.code ?? ''),
    titulo: String(raw.title ?? ''),
    tipo: String(raw.audit_type ?? ''),
    alcance: String(raw.scope ?? ''),
    plantaId: texto(raw.facility_id),
    estado: String(raw.status ?? 'planned') as EstadoAuditoria,
    inicioPlanificado: texto(raw.planned_start),
    finPlanificado: texto(raw.planned_end),
    inicioReal: texto(raw.actual_start),
    finReal: texto(raw.actual_end),
  };
}

export function preguntaDesdeApi(raw: Record<string, unknown>): Pregunta {
  return {
    id: String(raw.id),
    secuencia: Number(raw.sequence ?? 0),
    pregunta: String(raw.question ?? ''),
    resultado: String(raw.result ?? 'pending') as ResultadoPregunta,
    notas: String(raw.notes ?? ''),
    procesoId: texto(raw.process_id),
    articuloEvaluadoId: texto(raw.article_compliance_id),
    respondidaEl: texto(raw.assessed_at),
  };
}

/**
 * Una fecha del calendario (`AAAA-MM-DD`) como instante al **mediodía local**.
 *
 * `planned_start` es un instante. Mandar `2026-09-22` a secas lo deja a
 * medianoche UTC, que en Chile es el día anterior: la auditoría aparecería
 * planificada un día antes de lo elegido (el defecto de `lib/fechas.ts`). El
 * mediodía queda lejos de las dos medianoches.
 */
export function mediodiaLocal(fecha: string): string {
  return new Date(`${fecha}T12:00:00`).toISOString();
}

export interface NuevaAuditoria {
  codigo: string;
  titulo: string;
  tipo: TipoAuditoria;
  alcance: string;
  plantaId: string | null;
  /** `AAAA-MM-DD`, o vacío. */
  inicio: string;
  fin: string;
  auditorLiderId: string | null;
}

/** El cuerpo de `POST /audits/`, literal. `test_ciclo_de_auditoria.py` lo manda igual. */
export function cuerpoDeAuditoria(n: NuevaAuditoria) {
  return {
    code: n.codigo.trim(),
    title: n.titulo.trim(),
    audit_type: n.tipo,
    scope: n.alcance.trim(),
    facility_id: n.plantaId || null,
    planned_start: n.inicio ? mediodiaLocal(n.inicio) : null,
    planned_end: n.fin ? mediodiaLocal(n.fin) : null,
    lead_auditor_user_id: n.auditorLiderId || null,
  };
}

/** Un código que no choque con los que ya hay: `AUD-2026-004`. */
export function sugerirCodigo(existentes: readonly string[], anio: number): string {
  const prefijo = `AUD-${anio}-`;
  const usados = existentes
    .filter((c) => c.startsWith(prefijo))
    .map((c) => Number(c.slice(prefijo.length)))
    .filter((n) => Number.isInteger(n));
  const siguiente = (usados.length ? Math.max(...usados) : 0) + 1;
  return `${prefijo}${String(siguiente).padStart(3, '0')}`;
}

export async function crearAuditoria(tenantId: string, n: NuevaAuditoria): Promise<Record<string, unknown>> {
  return api.post<Record<string, unknown>>('/audits/', cuerpoDeAuditoria(n), { tenantId });
}

export async function listarCodigos(tenantId: string): Promise<string[]> {
  const filas = await api.get<Record<string, unknown>[]>('/audits/', { tenantId });
  return filas.map((f) => String(f.code ?? ''));
}

export async function leerAuditoria(tenantId: string, id: string): Promise<Auditoria> {
  return auditoriaDesdeApi(await api.get<Record<string, unknown>>(`/audits/${id}`, { tenantId }));
}

export async function avanzarAuditoria(
  tenantId: string,
  id: string,
  estado: EstadoAuditoria,
): Promise<Auditoria> {
  const raw = await api.post<Record<string, unknown>>(
    `/audits/${id}/advance?new_status=${estado}`,
    {},
    { tenantId },
  );
  return auditoriaDesdeApi(raw);
}

export async function cargarChecklist(tenantId: string, auditId: string): Promise<Pregunta[]> {
  const filas = await api.get<Record<string, unknown>[]>(`/audits/${auditId}/items`, { tenantId });
  return filas.map(preguntaDesdeApi).sort((a, b) => a.secuencia - b.secuencia);
}

export async function cargarCobertura(tenantId: string, auditId: string): Promise<Cobertura> {
  const c = await api.get<Record<string, unknown>>(`/audits/${auditId}/coverage`, { tenantId });
  return {
    aplicables: Number(c.aplicables ?? 0),
    cubiertos: Number(c.cubiertos ?? 0),
    porcentaje: c.porcentaje === null || c.porcentaje === undefined ? null : Number(c.porcentaje),
    preguntasSinArticulo: Number(c.items_sin_articulo ?? 0),
  };
}

/** El cuerpo de `POST /audits/{id}/items`. Sin `result`: una pregunta nace sin responder. */
export function cuerpoDePregunta(pregunta: string, procesoId: string | null) {
  return { question: pregunta.trim(), process_id: procesoId || null };
}

export async function agregarPregunta(
  tenantId: string,
  auditId: string,
  pregunta: string,
  procesoId: string | null,
): Promise<Pregunta> {
  const raw = await api.post<Record<string, unknown>>(
    `/audits/${auditId}/items`,
    cuerpoDePregunta(pregunta, procesoId),
    { tenantId },
  );
  return preguntaDesdeApi(raw);
}

/** El cuerpo del `PATCH`. `assessed_at` lo pone el servidor, no la pantalla. */
export function cuerpoDeRespuesta(resultado: ResultadoPregunta, notas: string) {
  return { result: resultado, notes: notas.trim() || null };
}

export async function responderPregunta(
  tenantId: string,
  auditId: string,
  itemId: string,
  resultado: ResultadoPregunta,
  notas: string,
): Promise<Pregunta> {
  const raw = await api.patch<Record<string, unknown>>(
    `/audits/${auditId}/items/${itemId}`,
    cuerpoDeRespuesta(resultado, notas),
    { tenantId },
  );
  return preguntaDesdeApi(raw);
}

export async function quitarPregunta(tenantId: string, auditId: string, itemId: string): Promise<void> {
  await api.delete(`/audits/${auditId}/items/${itemId}`, { tenantId });
}
