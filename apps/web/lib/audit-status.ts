import type { Audit, NonConformity } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms';

/**
 * Audit/NonConformity tienen sus propios estados (plazo de revisión vs.
 * hallazgo), distintos de ObligationStatus — se traducen al semáforo visual
 * existente sin agregar nuevos valores a StatusBadge (H4).
 */
export function auditSemaforo(estado: Audit['estado']): SemaforoStatus {
  switch (estado) {
    case 'cerrada':
      return 'cumple';
    case 'en_curso':
      return 'parcial';
    case 'planificada':
    default:
      return 'na';
  }
}

export function ncSemaforo(estado: NonConformity['estado']): SemaforoStatus {
  switch (estado) {
    case 'cerrada':
      return 'cumple';
    case 'en_tratamiento':
      return 'parcial';
    case 'abierta':
    default:
      return 'no_cumple';
  }
}

export const AUDIT_ESTADO_LABEL: Record<Audit['estado'], string> = {
  planificada: 'Planificada',
  en_curso: 'En curso',
  cerrada: 'Cerrada',
};

export const NC_ESTADO_LABEL: Record<NonConformity['estado'], string> = {
  abierta: 'Abierta',
  en_tratamiento: 'En tratamiento',
  cerrada: 'Cerrada',
};

export const CRITICIDAD_LABEL: Record<NonConformity['criticidad'], string> = {
  alta: 'Alta',
  media: 'Media',
  baja: 'Baja',
};
