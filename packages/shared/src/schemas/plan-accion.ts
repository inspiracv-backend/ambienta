import { z } from 'zod';

/**
 * El origen de un Plan de Acción puede ser un artículo de Matriz Legal
 * (Sección D), una tarea de Obligación (Sección E) o una No Conformidad
 * (Sección G, aún no implementada) — RF-19. Se modela genérico en vez de una
 * FK tipada por módulo porque los tres orígenes viven en secciones distintas
 * y no todas existen todavía.
 */
export const OrigenPlanAccionSchema = z.enum(['articulo', 'tarea_obligacion', 'no_conformidad']);
export type OrigenPlanAccion = z.infer<typeof OrigenPlanAccionSchema>;

export const PlanAccionTareaSchema = z.object({
  id: z.string(),
  titulo: z.string(),
  hecha: z.boolean().default(false),
});
export type PlanAccionTarea = z.infer<typeof PlanAccionTareaSchema>;

export const PlanAccionSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  origenTipo: OrigenPlanAccionSchema,
  origenId: z.string(),
  origenLabel: z.string(),
  titulo: z.string(),
  responsableId: z.string().optional(),
  fechaLimite: z.string(),
  estado: z.enum(['abierto', 'en_progreso', 'cerrado']),
  tareas: z.array(PlanAccionTareaSchema),
});
export type PlanAccion = z.infer<typeof PlanAccionSchema>;
