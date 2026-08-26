import type { LegalNorm, NonConformity, Obligation, Plant, Tenant, User } from '@ambienta/shared';

export interface ReportGeneratorProps {
  plants: Plant[];
  obligations: Obligation[];
  norms: LegalNorm[];
  nonConformities: NonConformity[];
  /**
   * La empresa auditada y quien emite, para el encabezado del documento.
   *
   * Opcionales porque los stores cargan de forma asincrona y la pantalla se
   * pinta antes. Mientras falten, **el PDF queda deshabilitado con su motivo a
   * la vista** en vez de emitir un documento sin identificacion: un informe sin
   * el nombre de la empresa no le sirve a nadie ante un fiscalizador.
   */
  tenant?: Tenant;
  usuario?: User;
}
