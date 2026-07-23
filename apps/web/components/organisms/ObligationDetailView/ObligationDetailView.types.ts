import type { Obligation } from '@ambienta/shared';

export interface ObligationDetailViewProps {
  obligation: Obligation;
  responsableOptions: { id: string; nombre: string }[];
}
