import type { NonConformity, Plant } from '@ambienta/shared';

export interface NonConformitiesListTableProps {
  nonConformities: NonConformity[];
  plants: Plant[];
}
