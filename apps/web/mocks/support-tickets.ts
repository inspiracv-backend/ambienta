import type { SupportTicket } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/** Tickets de soporte (RF-61) — entidad independiente del "ticket único" de Obligaciones/Calendario. */
export const mockSupportTickets: SupportTicket[] = [
  {
    id: 'ticket-1',
    numero: 'TCK-1042',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    tipoSolicitud: 'general',
    asunto: 'No puedo visualizar el certificado de un artículo',
    descripcion: 'Al intentar abrir la evidencia de la RCA de Rancagua, el enlace no carga.',
    estado: 'en_progreso',
    fecha: addDays(-4),
    contactoNombre: 'Camila Rojas',
    contactoEmail: 'camila.rojas@recicladorasur.cl',
    visibleParaCliente: true,
    correcciones: [],
  },
];
