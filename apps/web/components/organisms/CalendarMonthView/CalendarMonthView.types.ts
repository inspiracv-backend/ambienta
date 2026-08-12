import type { Obligation, ObligationTask } from '@ambienta/shared';

export interface TicketRef {
  obligation: Obligation;
  task: ObligationTask;
}

export interface CalendarMonthViewProps {
  tickets: TicketRef[];
  onSelectTicket: (ticket: TicketRef) => void;
}
