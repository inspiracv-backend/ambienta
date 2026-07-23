import { z } from 'zod';

export const AuditSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  plantId: z.string(),
  tipo: z.enum(['interna', 'externa']),
  fecha: z.string(),
  estado: z.enum(['planificada', 'en_curso', 'cerrada']),
  procesos: z.array(z.string()),
  normativaIds: z.array(z.string()),
});
export type Audit = z.infer<typeof AuditSchema>;

export const NonConformitySchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  auditId: z.string().optional(),
  hallazgo: z.string(),
  criticidad: z.enum(['alta', 'media', 'baja']),
  estado: z.enum(['abierta', 'en_tratamiento', 'cerrada']),
  fechaDeteccion: z.string(),
  responsableId: z.string(),
});
export type NonConformity = z.infer<typeof NonConformitySchema>;
