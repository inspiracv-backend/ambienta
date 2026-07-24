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

/**
 * RF-37: cierre con firma del responsable y fecha. No se modela como audit
 * log completo (gap transversal documentado, ver seccion-g-*.md) — solo el
 * cierre puntual que pide el RF.
 */
export const CierreNoConformidadSchema = z.object({
  fecha: z.string(),
  responsableId: z.string(),
  firmada: z.boolean(),
});
export type CierreNoConformidad = z.infer<typeof CierreNoConformidadSchema>;

export const NonConformitySchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  plantId: z.string(),
  auditId: z.string().optional(),
  hallazgo: z.string(),
  criticidad: z.enum(['alta', 'media', 'baja']),
  estado: z.enum(['abierta', 'en_tratamiento', 'cerrada']),
  fechaDeteccion: z.string(),
  responsableId: z.string(),
  /** Analisis de causa raiz (RF-35) — hasta 5 preguntas, se completa iterativamente. */
  cincoPorques: z.array(z.string()).max(5),
  cierre: CierreNoConformidadSchema.optional(),
});
export type NonConformity = z.infer<typeof NonConformitySchema>;
