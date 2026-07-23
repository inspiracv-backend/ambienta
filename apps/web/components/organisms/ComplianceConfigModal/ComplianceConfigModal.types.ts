import type { LegalNorm } from '@ambienta/shared';

export interface ComplianceConfigModalProps {
  norm: LegalNorm;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}
