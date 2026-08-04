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

/**
 * Descriptor de cargo (ISO 9001 §7.2 — Competencia).
 *
 * La norma exige determinar la competencia necesaria de las personas cuyo
 * trabajo afecta el desempeño del sistema de gestión, y conservar
 * información documentada como evidencia. El descriptor de cargo es el
 * documento donde eso vive habitualmente.
 *
 * El `rol` del sistema y el **cargo** de la persona son cosas distintas: el
 * rol define qué puede hacer en la aplicación, el cargo qué responsabilidades
 * tiene en la empresa. Un "Usuario Interno" puede ser Jefe de Planta o
 * Analista Ambiental, y en una auditoría lo que se revisa es lo segundo.
 */
export const DescriptorCargoSchema = z.object({
  cargo: z.string(),
  /** Qué hace. Se guarda como lista para poder auditarlas una por una. */
  funciones: z.array(z.string()).default([]),
  /** De qué responde ante el sistema de gestión. */
  responsabilidades: z.array(z.string()).default([]),
  /** Enlace al documento formal, si la empresa lo mantiene aparte. */
  documentoUrl: z.string().optional(),
});
export type DescriptorCargo = z.infer<typeof DescriptorCargoSchema>;

export const UserSchema = z.object({
  id: z.string(),
  tenantId: z.string().nullable(),
  nombre: z.string(),
  email: z.string().email(),
  role: RoleSchema,
  /** Cargo y competencias en la empresa — distinto del `role` del sistema (ISO 9001 §7.2). */
  descriptorCargo: DescriptorCargoSchema.optional(),
  /**
   * Permisos concedidos individualmente (RF-12). Si es `undefined`, aplican
   * los del rol: así los usuarios existentes no quedan sin permisos al
   * introducirse el modelo, y "no configurado" se distingue de "todo
   * revocado", que son cosas distintas para quien audita.
   */
  permisos: z.array(z.string()).optional(),
  plantIds: z.array(z.string()),
  /** RF-11 (v1.7): todo Usuario Interno pertenece obligatoriamente a un Departamento del Perfil Empresa. Null para los demás roles. */
  departamentoId: z.string().nullable(),
  estado: UserEstadoSchema,
  /** ISO date del último login conocido. Null si nunca ha iniciado sesión (ej. recién invitado). */
  ultimaActividad: z.string().nullable(),
  avatarUrl: z.string().optional(),
});
export type User = z.infer<typeof UserSchema>;
