import { z } from 'zod';

/** Departamento/Proceso del Perfil Empresa (RF-11, RF-12, v1.7) — todo Usuario Interno pertenece a uno. */
export const DepartamentoSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  nombre: z.string(),
});
export type Departamento = z.infer<typeof DepartamentoSchema>;
