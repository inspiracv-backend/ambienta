import { z } from 'zod';

/**
 * Ticket de Soporte (RF-61) — entidad independiente del "ticket único" de
 * Obligaciones/Calendario (Sección F). Mismo nombre en el lenguaje de
 * negocio, conceptos distintos: uno es una solicitud de ayuda, el otro un
 * plazo regulatorio. No comparten esquema ni store.
 */
export const CorreccionTicketSchema = z.object({
  fecha: z.string(),
  autorId: z.string(),
  nota: z.string(),
});
export type CorreccionTicket = z.infer<typeof CorreccionTicketSchema>;

export const SupportTicketSchema = z.object({
  id: z.string(),
  numero: z.string(),
  tenantId: z.string().nullable(),
  tipoSolicitud: z.string(),
  asunto: z.string(),
  descripcion: z.string(),
  estado: z.enum(['abierto', 'en_progreso', 'cerrado']),
  fecha: z.string(),
  contactoNombre: z.string().optional(),
  contactoEmail: z.string().optional(),
  /** RF-62: qué ve el cliente vs. el equipo interno. */
  visibleParaCliente: z.boolean(),
  /** RF-61: corrección de logs erróneos, con auditoría puntual del ticket. */
  correcciones: z.array(CorreccionTicketSchema),
});
export type SupportTicket = z.infer<typeof SupportTicketSchema>;
