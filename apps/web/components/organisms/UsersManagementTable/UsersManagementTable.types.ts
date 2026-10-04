import type { Departamento, Plant, User } from '@ambienta/shared';

export interface UsersManagementTableProps {
  users: User[];
  plants: Plant[];
  /** Departamentos **organizativos** (`/departments/`), no procesos. */
  departamentos: { id: string; nombre: string }[];
  tenantId: string;
  esGestorTenant: boolean;
  currentUserId: string;
}
