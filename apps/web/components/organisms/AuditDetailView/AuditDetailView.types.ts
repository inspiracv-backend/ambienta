import type { Audit, LegalNorm, NonConformity, Plant } from '@ambienta/shared';

export interface AuditDetailViewProps {
  audit: Audit;
  plant: Plant | undefined;
  normativas: LegalNorm[];
  hallazgos: NonConformity[];
}
