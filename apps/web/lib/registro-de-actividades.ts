'use client';

import { useEffect, useState } from 'react';
import type { AccionAuditable, AuditLogEntry, CambioCampo, EntidadAuditable } from '@ambienta/shared';
import { ENTIDAD_LABEL } from '@ambienta/shared';
import { api, mensajeDeError } from '@/lib/api-client';

/**
 * El registro de actividades **del servidor** (decisión 10 del 21-sep).
 *
 * `audit_log` se escribe solo desde el 24-ago y hasta el 21-sep **ninguna
 * pantalla lo leía**: `/historial` mostraba lo de la sesión del navegador y se
 * vaciaba al recargar. Acá se trae de `GET /system/audit-log` y se traduce a la
 * forma que la pantalla ya sabe mostrar.
 *
 * **Se carga en la pantalla y no en `audit-log-store`** porque ese provider
 * vive por encima de la sesión —a propósito, para que la sesión pueda
 * registrar sus eventos— y no sabe qué empresa pedir.
 */

/** Una fila tal como la devuelve la API. */
export interface FilaDelRegistro {
  id: number;
  tenant_id: string;
  occurred_at: string;
  actor_user_id: string | null;
  actor_nombre?: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  reason: string | null;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
}

/**
 * `audit_log.entity_type` guarda **el nombre de la tabla**, que es otro
 * vocabulario que el de los anclajes (`vocabulario-de-entidades.ts`). Lo que no
 * está acá va a `otro`: un evento que no se muestra es justo lo que un registro
 * de auditoría no puede hacer.
 */
export const ENTIDAD_POR_TABLA: Record<string, EntidadAuditable> = {
  support_tickets: 'ticket_soporte',
  obligations: 'obligacion',
  tasks: 'tarea',
  legal_norms: 'norma',
  matrix_norms: 'norma',
  article_compliance: 'articulo',
  nonconformities: 'no_conformidad',
  audits: 'auditoria',
  audit_items: 'auditoria',
  audit_process_results: 'auditoria',
  action_plans: 'plan_accion',
  users: 'usuario',
  user_roles: 'rol',
  user_permissions: 'rol',
  tenants: 'tenant',
  contracts: 'contrato',
  departments: 'departamento',
  processes: 'departamento',
  facilities: 'planta',
  environmental_aspects: 'aspecto_ambiental',
  risks_opportunities: 'riesgo_oportunidad',
  regulated_equipment: 'equipo',
  documents: 'documento',
  document_versions: 'documento',
  crm_companies: 'crm',
  crm_contacts: 'crm',
  crm_deals: 'crm',
  crm_activities: 'crm',
  crm_stages: 'crm',
  comments: 'comentario',
};

const ACCION_POR_VERBO: Record<string, AccionAuditable> = {
  create: 'creado',
  update: 'actualizado',
  delete: 'eliminado',
  download: 'exportado',
  approve: 'estado_cambiado',
  sync: 'actualizado',
  login: 'ingreso',
};

/** Los campos que suelen nombrar un registro, en orden de preferencia. */
const CAMPOS_DE_NOMBRE = ['title', 'titulo', 'name', 'legal_name', 'full_name', 'code', 'activity', 'email'];

function valor(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v.map((x) => valor(x) ?? '—').join(', ');
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function nombreDe(fila: FilaDelRegistro): string | null {
  for (const datos of [fila.after_data, fila.before_data]) {
    if (!datos) continue;
    for (const campo of CAMPOS_DE_NOMBRE) {
      const v = datos[campo];
      if (typeof v === 'string' && v.trim()) return v;
    }
  }
  return null;
}

export function entradaDesdeLaApi(fila: FilaDelRegistro, { tenantDePlataforma }: { tenantDePlataforma?: string | null } = {}): AuditLogEntry {
  const tipo = ENTIDAD_POR_TABLA[fila.entity_type] ?? 'otro';
  const accion = ACCION_POR_VERBO[fila.action] ?? 'actualizado';
  const corto = (fila.entity_id ?? '').slice(0, 8);
  const etiqueta =
    nombreDe(fila) ?? (tipo === 'otro' ? `${fila.entity_type} ${corto}` : `${ENTIDAD_LABEL[tipo]} ${corto}`).trim();

  const antes = fila.before_data ?? {};
  const despues = fila.after_data ?? {};
  const cambios: CambioCampo[] =
    accion === 'actualizado'
      ? Array.from(new Set([...Object.keys(antes), ...Object.keys(despues)])).map((campo) => ({
          campo,
          antes: valor(antes[campo]),
          despues: valor(despues[campo]),
        }))
      : [];

  let resumen: string;
  if (accion === 'exportado') {
    const filas = typeof despues.filas === 'number' ? `, ${despues.filas} filas` : '';
    const formato = typeof despues.formato === 'string' ? despues.formato.toUpperCase() : 'documento';
    resumen = `Emitió "${valor(despues.titulo) ?? etiqueta}" (${formato}${filas})`;
  } else if (accion === 'creado') {
    resumen = `Creó ${etiqueta}`;
  } else if (accion === 'eliminado') {
    resumen = `Eliminó ${etiqueta}`;
  } else if (accion === 'ingreso') {
    resumen = 'Ingresó al sistema';
  } else {
    resumen = cambios.length > 0 ? `Modificó ${cambios.map((c) => c.campo).join(', ')}` : `Modificó ${etiqueta}`;
  }

  return {
    id: `servidor-${fila.id}`,
    // Las filas de la empresa de la plataforma son "plataforma" para la
    // pantalla del Admin Global, que filtra esas por `tenantId: null`.
    tenantId: tenantDePlataforma && fila.tenant_id === tenantDePlataforma ? null : fila.tenant_id,
    entidadTipo: tipo,
    entidadId: fila.entity_id ?? '',
    entidadLabel: etiqueta,
    accion,
    resumen,
    cambios,
    actorId: fila.actor_user_id ?? 'sistema',
    // Sin actor es un proceso (o el modo de desarrollo). Con actor y sin nombre
    // es alguien que RLS no deja ver: una persona de otra empresa, un gestor.
    actorNombre: fila.actor_nombre ?? (fila.actor_user_id ? 'Persona de otra empresa' : 'Sistema'),
    actorRol: '',
    fecha: fila.occurred_at,
    ...(fila.reason ? { motivo: fila.reason } : {}),
  };
}

export interface Periodo {
  desde: string;
  hasta: string;
}

/**
 * Los últimos eventos del servidor, o los de un período. `hayMas` dice que la
 * página vino cortada: la pantalla lo muestra, porque una lista cortada en
 * silencio afirma que eso es todo lo que pasó.
 */
export function useRegistroDelServidor(
  tenantId: string | null,
  periodo: Periodo,
  { tenantDePlataforma }: { tenantDePlataforma?: string | null } = {},
) {
  const [entradas, setEntradas] = useState<AuditLogEntry[]>([]);
  const [hayMas, setHayMas] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (!tenantId) return;
    let cancelado = false;
    const params = new URLSearchParams({ limit: '500' });
    if (periodo.desde) params.set('desde', periodo.desde);
    if (periodo.hasta) params.set('hasta', periodo.hasta);
    setCargando(true);
    setError(null);
    api
      .getPagina<FilaDelRegistro>(`/system/audit-log?${params}`, { tenantId })
      .then(({ datos, hayMas: mas }) => {
        if (cancelado) return;
        setEntradas(datos.map((f) => entradaDesdeLaApi(f, { tenantDePlataforma })));
        setHayMas(mas);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(mensajeDeError(e));
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });
    return () => {
      cancelado = true;
    };
  }, [tenantId, periodo.desde, periodo.hasta, tenantDePlataforma]);

  return { entradas, hayMas, error, cargando };
}
