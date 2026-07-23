import type { Role } from '@ambienta/shared';

/** Nombres de rol tal como los define el Análisis Funcional v1.5 — nunca sinónimos inventados (H2). */
export const ROLE_LABEL: Record<Role, string> = {
  superadmin: 'Superadmin',
  admin_empresa: 'Admin Empresa',
  usuario_interno: 'Usuario Interno',
  cliente_invitado: 'Cliente Invitado',
  especialista: 'Especialista Ambiental',
  gestor: 'Gestor',
};
