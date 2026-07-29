import type { AuditLogEntry, EntidadAuditable } from '@ambienta/shared';

export interface FiltrosAuditoria {
  /** Busca en el resumen, la entidad y el nombre del actor. */
  texto: string;
  entidadTipo: EntidadAuditable | 'todas';
  actorId: string | 'todos';
  desde: string;
  hasta: string;
  /**
   * Solo lo usa el Superadmin: `'plataforma'` para su propia actividad, o el
   * id de una empresa para consultar la de ese cliente. Los roles de tenant
   * lo ignoran — su alcance lo fija el rol, no un filtro.
   */
  tenantId: string | 'plataforma';
}

export const FILTROS_INICIALES: FiltrosAuditoria = {
  texto: '',
  entidadTipo: 'todas',
  actorId: 'todos',
  desde: '',
  hasta: '',
  tenantId: 'plataforma',
};

function enRango(iso: string, desde: string, hasta: string): boolean {
  if (!desde && !hasta) return true;
  const t = new Date(iso).getTime();
  if (desde && t < new Date(desde).getTime()) return false;
  // El día "hasta" cuenta completo: quien filtra "hasta el 30" espera que
  // incluya lo que pasó ese día, no hasta su medianoche. Mismo criterio que
  // `lib/reports.ts`.
  if (hasta && t > new Date(hasta).getTime() + 86_400_000 - 1) return false;
  return true;
}

/**
 * Filtra el historial para la vista consolidada (RNF-26: los logs deben poder
 * exportarse y consultarse para auditorías externas).
 *
 * El aislamiento por tenant se aplica **antes** que cualquier otro filtro y no
 * es opcional: un Admin Empresa nunca debe ver actividad de otra empresa,
 * aunque busque por texto. En el backend esto lo garantiza RLS; aquí es una
 * condición explícita para que el comportamiento sea el mismo.
 */
export function filtrarAuditoria(
  entries: AuditLogEntry[],
  tenantIdVisible: string | null,
  filtros: FiltrosAuditoria,
): AuditLogEntry[] {
  const texto = filtros.texto.trim().toLowerCase();

  return entries
    .filter((e) => {
      // `null` = Superadmin. Por defecto ve la actividad de plataforma, pero
      // puede pedir la de una empresa concreta: la matriz de permisos le
      // concede lectura ("L") sobre los tenants para soporte y auditoría.
      // Lectura, nunca edición — CLAUDE.md: "Admin Global NO puede editar
      // contenido de tenants".
      if (tenantIdVisible === null) {
        return filtros.tenantId === 'plataforma' ? e.tenantId === null : e.tenantId === filtros.tenantId;
      }
      // Los roles de tenant solo ven la suya, sin excepción.
      return e.tenantId === tenantIdVisible;
    })
    .filter((e) => filtros.entidadTipo === 'todas' || e.entidadTipo === filtros.entidadTipo)
    .filter((e) => filtros.actorId === 'todos' || e.actorId === filtros.actorId)
    .filter((e) => enRango(e.fecha, filtros.desde, filtros.hasta))
    .filter((e) => {
      if (!texto) return true;
      return (
        e.resumen.toLowerCase().includes(texto) ||
        e.entidadLabel.toLowerCase().includes(texto) ||
        e.actorNombre.toLowerCase().includes(texto) ||
        (e.motivo?.toLowerCase().includes(texto) ?? false)
      );
    })
    .sort((a, b) => new Date(b.fecha).getTime() - new Date(a.fecha).getTime());
}

/** Actores presentes en un conjunto de eventos, para poblar el filtro. */
export function actoresDe(entries: AuditLogEntry[]): Array<{ id: string; nombre: string }> {
  // `Array.from` en vez de spread sobre el iterador: el target de TypeScript
  // del proyecto no habilita `downlevelIteration`.
  const mapa = new Map<string, string>();
  for (const e of entries) mapa.set(e.actorId, e.actorNombre);
  return Array.from(mapa, ([id, nombre]) => ({ id, nombre })).sort((a, b) =>
    a.nombre.localeCompare(b.nombre, 'es'),
  );
}

function csvEscape(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

/**
 * Exporta el historial a CSV (RNF-26).
 *
 * Los cambios se aplanan a una sola celda legible ("Estado: Abierto → Cerrado")
 * en vez de JSON: el destinatario de este archivo es un auditor externo con
 * Excel, no un sistema.
 */
export function exportarAuditoriaCsv(entries: AuditLogEntry[]): string {
  const headers = ['Fecha', 'Actor', 'Rol', 'Acción', 'Entidad', 'Detalle', 'Cambios', 'Motivo', 'Aprobado por'];

  const rows = entries.map((e) => [
    new Date(e.fecha).toLocaleString('es-CL'),
    e.actorNombre,
    e.actorRol,
    e.accion,
    e.entidadLabel,
    e.resumen,
    e.cambios.map((c) => `${c.campo}: ${c.antes ?? 'vacío'} → ${c.despues ?? 'vacío'}`).join(' | '),
    e.motivo ?? '',
    e.aprobadoPorNombre ?? '',
  ]);

  return [headers, ...rows].map((row) => row.map(csvEscape).join(',')).join('\n');
}
