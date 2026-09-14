import type { Audit, LegalNorm, NonConformity, Plant } from '@ambienta/shared';

export interface AuditDetailViewProps {
  audit: Audit;
  plant: Plant | undefined;
  /** `null` = no se sabe cuáles son; la sección no se muestra en vez de decir «ninguna». */
  normativas: LegalNorm[] | null;
  /** `null` = todavía cargando; un texto = no se pudo preguntar. */
  hallazgos: NonConformity[] | null;
  errorHallazgos?: string | null;
}
