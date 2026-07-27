import { z } from 'zod';

/**
 * 5 actores del Análisis Funcional v1.7 (Notion, 27-jul-2026). El rol
 * "Especialista" del v1.5 fue eliminado (Decisión cerrada #12, v1.7): se
 * cubre con Usuario Interno + RBAC. No confundir con los 3 roles listados
 * en CLAUDE.md, que quedaron desactualizados respecto al funcional — ver
 * auditoria-stack-frontend.md y openspec/analisis/seccion-a-autenticacion.md.
 */
export const RoleSchema = z.enum([
  'superadmin',
  'admin_empresa',
  'usuario_interno',
  'cliente_invitado',
  'gestor',
]);
export type Role = z.infer<typeof RoleSchema>;

/** Estado de cuenta del usuario dentro del tenant (S-41, Sección N). "invitado" = invitación creada pero sin primer login (no hay envío real de email, ver gap). */
export const UserEstadoSchema = z.enum(['activo', 'invitado', 'desactivado']);
export type UserEstado = z.infer<typeof UserEstadoSchema>;

export const UserSchema = z.object({
  id: z.string(),
  tenantId: z.string().nullable(),
  nombre: z.string(),
  email: z.string().email(),
  role: RoleSchema,
  plantIds: z.array(z.string()),
  /** RF-11 (v1.7): todo Usuario Interno pertenece obligatoriamente a un Departamento del Perfil Empresa. Null para los demás roles. */
  departamentoId: z.string().nullable(),
  estado: UserEstadoSchema,
  /** ISO date del último login conocido. Null si nunca ha iniciado sesión (ej. recién invitado). */
  ultimaActividad: z.string().nullable(),
  avatarUrl: z.string().optional(),
});
export type User = z.infer<typeof UserSchema>;
