import { z } from 'zod';

/**
 * 6 actores del Análisis Funcional v1.5 (Notion, 2026-07-23).
 * No confundir con los 3 roles listados en CLAUDE.md, que quedaron
 * desactualizados respecto al funcional — ver auditoria-stack-frontend.md
 * y openspec/analisis/seccion-a-autenticacion.md.
 */
export const RoleSchema = z.enum([
  'superadmin',
  'admin_empresa',
  'usuario_interno',
  'cliente_invitado',
  'especialista',
  'gestor',
]);
export type Role = z.infer<typeof RoleSchema>;

export const UserSchema = z.object({
  id: z.string(),
  tenantId: z.string().nullable(),
  nombre: z.string(),
  email: z.string().email(),
  role: RoleSchema,
  plantIds: z.array(z.string()),
  avatarUrl: z.string().optional(),
});
export type User = z.infer<typeof UserSchema>;
