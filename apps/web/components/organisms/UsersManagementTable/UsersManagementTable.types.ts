import type { Departamento, Plant, User } from '@ambienta/shared';

export interface UsersManagementTableProps {
  users: User[];
  plants: Plant[];
  departamentos: Departamento[];
  tenantId: string;
  esGestorTenant: boolean;
  currentUserId: string;
}
