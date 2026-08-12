import type { LegalNorm, NonConformity, Obligation, Plant } from '@ambienta/shared';

export interface ReportGeneratorProps {
  plants: Plant[];
  obligations: Obligation[];
  norms: LegalNorm[];
  nonConformities: NonConformity[];
}
