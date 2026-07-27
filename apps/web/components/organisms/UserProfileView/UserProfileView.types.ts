import type { User } from '@ambienta/shared';

export interface UserProfileViewProps {
  user: User;
  tenantNombre: string;
  onUpdateNombre: (nombre: string) => void;
}
