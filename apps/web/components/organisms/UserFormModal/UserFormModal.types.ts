import type { Departamento, Plant, Role, User } from '@ambienta/shared';

export interface UserFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Si viene definido, el modal edita este usuario; si no, invita uno nuevo. */
  user?: User;
  tenantId: string;
  esGestorTenant: boolean;
  plants: Plant[];
  departamentos: Departamento[];
}

export type AssignableRole = Extract<Role, 'admin_empresa' | 'usuario_interno' | 'gestor'>;
