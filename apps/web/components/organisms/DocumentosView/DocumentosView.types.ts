import type { Documento, RevisionDocumental } from '@ambienta/shared';

export interface DocumentosListaProps {
  documentos: Documento[];
  seleccionadoId: string | null;
  onSeleccionar: (id: string) => void;
}

export interface RevisionesPanelProps {
  documento: Documento;
  revisiones: RevisionDocumental[] | undefined;
  cargando: boolean;
}

export interface CrearDocumentoModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreado: (id: string) => void;
}
