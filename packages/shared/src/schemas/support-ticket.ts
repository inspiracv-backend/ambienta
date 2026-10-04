import { z } from 'zod';

/**
 * Ticket de Soporte (RF-61) — entidad independiente del "ticket único" de
 * Obligaciones/Calendario (Sección F). Mismo nombre en el lenguaje de
 * negocio, conceptos distintos: uno es una solicitud de ayuda, el otro un
 * plazo regulatorio. No comparten esquema ni store.
 */
/**
 * RF-83: una corrección de un registro erróneo. **Vive en la base** como un
 * mensaje `internal_note` del ticket, y no se edita después (la API responde
 * 409). Se carga aparte, al abrir el ticket: no viene en el listado.
 */
export const CorreccionTicketSchema = z.object({
  id: z.string(),
  fecha: z.string(),
  autorId: z.string().nullable(),
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
  // `visibleParaCliente` se quitó el 13-sep: la base no tiene ese campo y la
  // pantalla lo mostraba siempre en `true`, con un botón que no guardaba. La
  // distinción real de RF-84 es por mensaje (`is_internal`), no por ticket.
});
export type SupportTicket = z.infer<typeof SupportTicketSchema>;
