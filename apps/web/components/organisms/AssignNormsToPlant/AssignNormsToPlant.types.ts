import type { LegalNorm, Plant } from '@ambienta/shared';

export interface AssignNormsToPlantProps {
  plants: Plant[];
  norms: LegalNorm[];
}
