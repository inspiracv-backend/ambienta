import type { LegalNorm } from '@ambienta/shared';

export interface CatalogNormsTableProps {
  norms: LegalNorm[];
  tenantPlantIds: string[];
  isSuperadmin: boolean;
  isAdminEmpresa: boolean;
  onMarcarAplicable: (normId: string) => void;
}
