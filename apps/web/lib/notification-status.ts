import type { Urgencia } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms';

/** Urgencia de notificación (RF-31) mapeada al semáforo existente (H4). */
export function urgenciaSemaforo(urgencia: Urgencia): SemaforoStatus {
  switch (urgencia) {
    case 'alta':
      return 'no_cumple';
    case 'media':
      return 'parcial';
    case 'baja':
    default:
      return 'cumple';
  }
}

export const URGENCIA_LABEL: Record<Urgencia, string> = {
  alta: 'Urgente',
  media: 'Próximo',
  baja: 'Informativo',
};
