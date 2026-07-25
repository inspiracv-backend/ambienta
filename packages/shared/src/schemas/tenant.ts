import { z } from 'zod';

export const PlantSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  nombre: z.string(),
  comuna: z.string(),
  region: z.string(),
});
export type Plant = z.infer<typeof PlantSchema>;

/** Módulos administrables por el Superadmin (RF-59) — coinciden con la navegación global de la plataforma. */
export const MODULOS_PLATAFORMA = [
  'matriz-legal',
  'obligaciones',
  'calendario',
  'auditorias',
  'no-conformidades',
  'catalogo-normativo',
  'gestores',
  'reportes',
  'notificaciones',
  'usuarios-roles',
  'chatbot',
] as const;
export const ModuloPlataformaSchema = z.enum(MODULOS_PLATAFORMA);
export type ModuloPlataforma = z.infer<typeof ModuloPlataformaSchema>;

export const TenantSchema = z.object({
  id: z.string(),
  nombre: z.string(),
  rut: z.string(),
  sector: z.string(),
  esGestor: z.boolean().default(false),
  /** Campos de administración de plataforma (RF-59) — nunca contenido de negocio del tenant (CLAUDE.md: Superadmin no edita contenido de tenants). */
  estado: z.enum(['activo', 'suspendido']),
  limiteUsuarios: z.number(),
  modulosActivos: z.array(ModuloPlataformaSchema),
  plants: z.array(PlantSchema),
});
export type Tenant = z.infer<typeof TenantSchema>;
