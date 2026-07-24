import type { NonConformity, Plant } from '@ambienta/shared';

export interface NonConformityDetailViewProps {
  nonConformity: NonConformity;
  plant: Plant | undefined;
  responsableOptions: { id: string; nombre: string }[];
}
