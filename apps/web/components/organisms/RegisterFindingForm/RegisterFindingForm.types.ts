import type { Plant } from '@ambienta/shared';

export interface RegisterFindingFormProps {
  tenantId: string;
  plants: Plant[];
  responsableOptions: { id: string; nombre: string }[];
  defaultPlantId?: string;
  defaultAuditId?: string;
  /** La pregunta del checklist de la que sale el hallazgo, si se llega desde ella. */
  defaultAuditItemId?: string;
}
