import type { TicketRef } from '@/components/organisms/CalendarMonthView';

export interface GanttViewProps {
  tickets: TicketRef[];
  onSelectTicket: (ticket: TicketRef) => void;
}
