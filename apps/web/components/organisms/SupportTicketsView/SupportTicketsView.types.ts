import type { SupportTicket } from '@ambienta/shared';

export interface SupportTicketsViewProps {
  tickets: SupportTicket[];
  tenantNombre: (tenantId: string | null) => string;
  currentUserId: string;
}
