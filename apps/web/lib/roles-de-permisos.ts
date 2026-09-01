/**
 * El rol que decide qué puede hacer una persona (#140, RF-08).
 *
 * ## Por qué esto no es el `role` que ya existe
 *
 * En este repositorio conviven **dos** nociones de rol, y confundirlas cuesta
 * caro:
 *
 * | | De dónde sale | Para qué sirve |
 * |---|---|---|
 * | `User.role` | `users.user_type` | **Qué clase de cuenta es**: decide el menú, si pertenece a un departamento, si es invitado |
 * | Rol de permisos | `user_roles` → `roles.code` | **Qué puede hacer**: es lo único que la guarda de cada ruta consulta |
 *
 * La migración `09_roles_por_codigo.sql` derivó el segundo del primero **una
 * vez**, para que nadie quedara sin permisos al encender la guarda. Después son
 * independientes: cambiar uno no cambia el otro.
 *
 * Este módulo administra **el segundo**, que es el que concede permisos. No
 * toca `user_type`: mezclarlos convertiría «dale permiso de administrar» en
 * «conviértela en administradora de la plataforma».
 *
 * Hasta ahora `updateRole` mostraba un aviso diciendo que el cambio no se
 * guardaba — y era verdad: `user_roles` no tenía ni una ruta.
 */
import { api, mensajeDeError } from '@/lib/api-client';

export interface RolDePermisos {
  id: string;
  codigo: string;
  nombre: string;
  descripcion: string | null;
}

/** Lo que una persona tiene hoy. */
export interface RolesDeUnaPersona {
  ids: string[];
  codigos: string[];
}

export interface ResultadoDeRoles extends RolesDeUnaPersona {
  ok: boolean;
  /** Qué cambió: roles asignados, retirados o reabiertos. */
  efectos: string[];
  error?: string;
}

function texto(v: unknown): string {
  return v === null || v === undefined ? '' : String(v);
}

export function mapRol(raw: Record<string, unknown>): RolDePermisos {
  return {
    id: texto(raw.id),
    codigo: texto(raw.code),
    nombre: texto(raw.name),
    descripcion: raw.description ? String(raw.description) : null,
  };
}

/** El catálogo de la empresa, para poder ofrecer un selector. */
export async function cargarRoles(tenantId: string): Promise<RolDePermisos[]> {
  const filas = await api.get<Record<string, unknown>[]>('/roles/', { tenantId });
  return Array.isArray(filas) ? filas.map(mapRol) : [];
}

/**
 * Los roles **vigentes** de una persona.
 *
 * Solo los vigentes: un rol vencido no concede nada, y mostrarlo junto a los
 * activos haría creer que conserva permisos que ya se le retiraron.
 */
export async function cargarRolesDe(
  tenantId: string,
  userId: string,
): Promise<RolesDeUnaPersona> {
  const raw = await api.get<Record<string, unknown>>(`/users/${userId}/roles`, {
    tenantId,
  });
  return {
    ids: Array.isArray(raw.role_ids) ? raw.role_ids.map(String) : [],
    codigos: Array.isArray(raw.codigos) ? raw.codigos.map(String) : [],
  };
}

/**
 * Deja a la persona **exactamente** con esos roles.
 *
 * Es un `PUT` porque el cuerpo describe el estado final. La API puede
 * responder **409** cuando el cambio dejaría a la empresa sin nadie que pueda
 * administrar usuarios — ese mensaje se devuelve tal cual, porque explica qué
 * hacer para poder seguir y uno genérico no.
 */
export async function fijarRoles(
  tenantId: string,
  userId: string,
  roleIds: string[],
): Promise<ResultadoDeRoles> {
  try {
    const raw = await api.put<Record<string, unknown>>(
      `/users/${userId}/roles`,
      { role_ids: roleIds },
      { tenantId },
    );
    return {
      ok: true,
      ids: Array.isArray(raw.role_ids) ? raw.role_ids.map(String) : [],
      codigos: Array.isArray(raw.codigos) ? raw.codigos.map(String) : [],
      efectos: Array.isArray(raw.efectos) ? raw.efectos.map(String) : [],
    };
  } catch (e) {
    return { ok: false, ids: [], codigos: [], efectos: [], error: mensajeDeError(e) };
  }
}
