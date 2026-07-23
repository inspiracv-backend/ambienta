import type { Articulo, RespuestaCumplimiento } from '@ambienta/shared';

export interface ArticleEvaluationModalProps {
  articulo: Articulo | null;
  normId: string;
  normNombre: string;
  tenantId: string;
  responsableOptions: { id: string; nombre: string }[];
  onOpenChange: (open: boolean) => void;
}

export type { RespuestaCumplimiento };
