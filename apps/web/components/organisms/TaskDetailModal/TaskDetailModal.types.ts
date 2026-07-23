import type { ObligationTask } from '@ambienta/shared';

export interface TaskDetailModalProps {
  task: ObligationTask | null;
  obligationId: string;
  obligationNombre: string;
  tenantId: string;
  responsableOptions: { id: string; nombre: string }[];
  onOpenChange: (open: boolean) => void;
}
