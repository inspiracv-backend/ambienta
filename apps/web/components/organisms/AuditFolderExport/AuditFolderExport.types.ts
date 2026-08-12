import type { Audit, NonConformity, Plant } from '@ambienta/shared';

export interface AuditFolderExportProps {
  audits: Audit[];
  plants: Plant[];
  nonConformities: NonConformity[];
}
