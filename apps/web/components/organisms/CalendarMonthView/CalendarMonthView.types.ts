import type { Obligation, ObligationTask } from '@ambienta/shared';
import type { EventoDeCalendario } from '@/lib/eventos-de-calendario';

export interface TicketRef {
  obligation: Obligation;
  task: ObligationTask;
}

export interface CalendarMonthViewProps {
  tickets: TicketRef[];
  onSelectTicket: (ticket: TicketRef) => void;
  /** Lo que vence y no es una tarea: revisiones de normas e inscripciones de
      equipos. Llevan a su pantalla, no abren el ticket. */
  eventos?: EventoDeCalendario[];
}
