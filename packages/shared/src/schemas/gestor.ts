import { z } from 'zod';

export const ContactoSchema = z.object({
  id: z.string(),
  nombre: z.string(),
  cargo: z.string(),
  telefono: z.string(),
  email: z.string().email(),
  autorizado: z.boolean(),
});
export type Contacto = z.infer<typeof ContactoSchema>;

/** Cliente final de un tenant Gestor (RF-56/RF-57, sub-tenancy). */
export const SubTenantSchema = z.object({
  id: z.string(),
  gestorTenantId: z.string(),
  nombre: z.string(),
  rut: z.string(),
  estado: z.enum(['activo', 'inactivo']),
  contactos: z.array(ContactoSchema),
});
export type SubTenant = z.infer<typeof SubTenantSchema>;

/**
 * Campos customizables por tenant (RF-58b) — se modela como par clave-valor
 * simple; la decisión formal de un enfoque más avanzado (tipo CRM) sigue
 * pendiente (ver decisión #4 del Análisis Funcional v1.5).
 */
export const ContratoSchema = z.object({
  id: z.string(),
  subTenantId: z.string(),
  nombre: z.string(),
  fechaInicio: z.string(),
  fechaTermino: z.string(),
  camposCustom: z.record(z.string(), z.string()),
  archivoUrl: z.string().optional(),
});
export type Contrato = z.infer<typeof ContratoSchema>;
