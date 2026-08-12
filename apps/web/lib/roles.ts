import type { Role } from '@ambienta/shared';

/** Nombres de rol tal como los define el Análisis Funcional v1.7 — nunca sinónimos inventados (H2). */
export const ROLE_LABEL: Record<Role, string> = {
  superadmin: 'Superadmin',
  admin_empresa: 'Admin Empresa',
  usuario_interno: 'Usuario Interno',
  cliente_invitado: 'Cliente Invitado',
  gestor: 'Gestor',
};

/** Descripción breve por rol para el selector de "Invitar usuario" (S-41, H10). */
export const ROLE_DESCRIPTION: Record<Role, string> = {
  superadmin: 'Administra la plataforma completa — no se asigna desde un tenant.',
  admin_empresa: 'Gestión completa de la empresa: usuarios, matriz legal, obligaciones y reportes.',
  usuario_interno: 'Opera según los permisos de su departamento y sus plantas asignadas.',
  cliente_invitado: 'Acceso limitado a tickets — se genera vía el flujo de invitado, no por invitación directa.',
  gestor: 'Administra clientes (sub-tenants), contratos y declaraciones de residuos.',
};
