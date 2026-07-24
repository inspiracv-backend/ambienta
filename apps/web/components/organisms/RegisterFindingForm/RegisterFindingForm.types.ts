import type { Plant } from '@ambienta/shared';

export interface RegisterFindingFormProps {
  tenantId: string;
  plants: Plant[];
  responsableOptions: { id: string; nombre: string }[];
  defaultPlantId?: string;
  defaultAuditId?: string;
}
