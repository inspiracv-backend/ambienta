import { z } from 'zod';

export const PlantSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  nombre: z.string(),
  comuna: z.string(),
  region: z.string(),
});
export type Plant = z.infer<typeof PlantSchema>;

export const TenantSchema = z.object({
  id: z.string(),
  nombre: z.string(),
  rut: z.string(),
  sector: z.string(),
  esGestor: z.boolean().default(false),
  plants: z.array(PlantSchema),
});
export type Tenant = z.infer<typeof TenantSchema>;
