import type { TicketRef } from '@/components/organisms/CalendarMonthView';

export interface KanbanBoardProps {
  tickets: TicketRef[];
  onSelectTicket: (ticket: TicketRef) => void;
}
