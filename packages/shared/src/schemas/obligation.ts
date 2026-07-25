import { z } from 'zod';

export const SistemaDeclaracionSchema = z.enum([
  'RETC',
  'Ley REP',
  'SINADER',
  'SIDREP',
  'DAE',
]);
export type SistemaDeclaracion = z.infer<typeof SistemaDeclaracionSchema>;

export const ObligationStatusSchema = z.enum([
  'vigente',
  'por_vencer',
  'vencida',
  'sin_evidencia',
]);
export type ObligationStatus = z.infer<typeof ObligationStatusSchema>;

export const ObligationTaskSchema = z.object({
  id: z.string(),
  obligationId: z.string(),
  titulo: z.string(),
  vencimiento: z.string(),
  responsableId: z.string(),
  estado: ObligationStatusSchema,
  evidenciaUrl: z.string().optional(),
});
export type ObligationTask = z.infer<typeof ObligationTaskSchema>;

/** Cada declaración periódica se modela como "megaproyecto" (RF-15). */
export const ObligationSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  plantId: z.string(),
  sistema: SistemaDeclaracionSchema,
  nombre: z.string(),
  periodo: z.string(),
  estado: ObligationStatusSchema,
  proximoVencimiento: z.string(),
  responsableId: z.string(),
  tasks: z.array(ObligationTaskSchema),
  /** Declaración de un cliente final de un tenant Gestor (RF-57, Sección I) — ausente para tenants no-Gestor. */
  subTenantId: z.string().optional(),
});
export type Obligation = z.infer<typeof ObligationSchema>;
