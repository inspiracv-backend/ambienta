import type { Sincronizacion } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms';

/** Estado de sincronización del agente BCN (RF-45) mapeado al semáforo existente (H4). */
export function syncSemaforo(estado: Sincronizacion['estado']): SemaforoStatus {
  switch (estado) {
    case 'sincronizado':
      return 'cumple';
    case 'desactualizado':
      return 'parcial';
    case 'error':
    default:
      return 'no_cumple';
  }
}

export const SYNC_LABEL: Record<Sincronizacion['estado'], string> = {
  sincronizado: 'Sincronizado',
  desactualizado: 'Desactualizado',
  error: 'Error de sincronización',
};

export const FUENTE_LABEL = { BCN: 'Pública (BCN)', ISO: 'ISO interna', RCA: 'RCA del tenant' } as const;
