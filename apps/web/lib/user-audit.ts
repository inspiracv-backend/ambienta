import type { CambioCampo, Departamento, Plant, Role, User, UserEstado } from '@ambienta/shared';
import type { EventoAuditable } from '@/lib/audit-log-store';
import { ROLE_LABEL } from '@/lib/roles';

const ESTADO_USUARIO_LABEL: Record<UserEstado, string> = {
  activo: 'Activo',
  invitado: 'Invitado',
  desactivado: 'Desactivado',
};

/**
 * Construye los eventos de auditoría del flujo de usuarios (Sección N).
 *
 * Vive aparte porque `UsersProvider` no puede registrar por sí mismo: está por
 * encima de `SessionProvider`, así que no tiene actor (ver el comentario en
 * `users-store.tsx`). Centralizar el formato aquí evita que cada pantalla que
 * edite usuarios invente su propia redacción y el historial quede inconsistente.
 *
 * Cambiar el rol de alguien es una decisión de seguridad: es el equivalente a
 * darle o quitarle llaves. Por eso se registra el rol anterior y el nuevo con
 * su nombre legible, no el identificador interno.
 */

export function eventoUsuarioInvitado(nuevo: User): EventoAuditable {
  return {
    entidadTipo: 'usuario',
    entidadId: nuevo.id,
    entidadLabel: `${nuevo.nombre} (${nuevo.email})`,
    tenantId: nuevo.tenantId,
    accion: 'creado',
    resumen: `Invitó a ${nuevo.nombre}`,
    cambios: [
      { campo: 'Rol', antes: null, despues: ROLE_LABEL[nuevo.role] },
      { campo: 'Estado', antes: null, despues: ESTADO_USUARIO_LABEL[nuevo.estado] },
    ],
  };
}

export function eventoCambioDeRol(user: User, roleAnterior: Role, roleNuevo: Role): EventoAuditable {
  return {
    entidadTipo: 'usuario',
    entidadId: user.id,
    entidadLabel: `${user.nombre} (${user.email})`,
    tenantId: user.tenantId,
    accion: 'actualizado',
    resumen: `Cambió el rol de ${user.nombre}`,
    cambios: [{ campo: 'Rol', antes: ROLE_LABEL[roleAnterior], despues: ROLE_LABEL[roleNuevo] }],
  };
}

export function eventoCambioDeEstado(user: User, estadoAnterior: UserEstado, estadoNuevo: UserEstado): EventoAuditable {
  return {
    entidadTipo: 'usuario',
    entidadId: user.id,
    entidadLabel: `${user.nombre} (${user.email})`,
    tenantId: user.tenantId,
    accion: estadoNuevo === 'desactivado' ? 'suspendido' : 'reactivado',
    resumen:
      estadoNuevo === 'desactivado' ? `Desactivó la cuenta de ${user.nombre}` : `Reactivó la cuenta de ${user.nombre}`,
    cambios: [
      { campo: 'Estado', antes: ESTADO_USUARIO_LABEL[estadoAnterior], despues: ESTADO_USUARIO_LABEL[estadoNuevo] },
    ],
  };
}

export function eventoCambioDePlantas(user: User, antes: string[], despues: string[], plants: Plant[]): EventoAuditable {
  const nombres = (ids: string[]) =>
    ids.map((id) => plants.find((p) => p.id === id)?.nombre ?? id).join(', ') || 'Ninguna';

  return {
    entidadTipo: 'usuario',
    entidadId: user.id,
    entidadLabel: `${user.nombre} (${user.email})`,
    tenantId: user.tenantId,
    accion: 'asignado',
    resumen: `Cambió las plantas asignadas a ${user.nombre}`,
    // Nombres y no ids: quien audita no conoce los identificadores internos.
    cambios: [{ campo: 'Plantas', antes: nombres(antes), despues: nombres(despues) }],
  };
}

export function eventoCambioDeDepartamento(
  user: User,
  antes: string | null,
  despues: string | null,
  departamentos: Departamento[],
): EventoAuditable {
  const nombre = (id: string | null) =>
    id ? (departamentos.find((d) => d.id === id)?.nombre ?? id) : null;

  return {
    entidadTipo: 'usuario',
    entidadId: user.id,
    entidadLabel: `${user.nombre} (${user.email})`,
    tenantId: user.tenantId,
    accion: 'asignado',
    resumen: `Cambió el departamento de ${user.nombre}`,
    cambios: [{ campo: 'Departamento', antes: nombre(antes), despues: nombre(despues) }],
  };
}

export function eventoCambioDeNombre(user: User, antes: string, despues: string): EventoAuditable {
  return {
    entidadTipo: 'usuario',
    entidadId: user.id,
    entidadLabel: `${despues} (${user.email})`,
    tenantId: user.tenantId,
    accion: 'actualizado',
    resumen: 'Actualizó su nombre',
    cambios: [{ campo: 'Nombre', antes, despues }] satisfies CambioCampo[],
  };
}
