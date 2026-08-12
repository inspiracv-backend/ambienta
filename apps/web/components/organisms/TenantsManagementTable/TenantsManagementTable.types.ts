import type { Tenant } from '@ambienta/shared';

export interface TenantsManagementTableProps {
  tenants: Tenant[];
  userCounts: Record<string, number>;
}
