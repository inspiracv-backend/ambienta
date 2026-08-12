import type { Plant } from '@ambienta/shared';

export interface CreateObligationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plants: Plant[];
}
