import type { LegalNorm } from '@ambienta/shared';

export interface NormDetailViewProps {
  norm: LegalNorm;
  /** Tenant activo de la sesión — distinto de `norm.tenantId`, que es null para normas públicas (BCN). */
  activeTenantId: string;
  responsableOptions: { id: string; nombre: string }[];
}
