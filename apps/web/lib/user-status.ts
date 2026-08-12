import type { UserEstado } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms';

/** UserEstado (activo/invitado/desactivado) traducido al semáforo visual existente (S-41, H4). */
export function userSemaforo(estado: UserEstado): SemaforoStatus {
  switch (estado) {
    case 'activo':
      return 'cumple';
    case 'invitado':
      return 'pendiente';
    case 'desactivado':
    default:
      return 'no_cumple';
  }
}

export const USER_ESTADO_LABEL: Record<UserEstado, string> = {
  activo: 'Activo',
  invitado: 'Invitado',
  desactivado: 'Desactivado',
};
