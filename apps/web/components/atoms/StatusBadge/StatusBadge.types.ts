/**
 * Semáforo único de la plataforma (H2 + H4): siempre ícono + color + texto,
 * nunca solo color. Reutilizado por Dashboard, Matriz Legal, Obligaciones,
 * Calendario — un solo átomo para todas las pantallas.
 */
export type SemaforoStatus =
  | 'cumple'
  | 'parcial'
  | 'no_cumple'
  | 'na'
  | 'pendiente'
  | 'vigente'
  | 'por_vencer'
  | 'vencida'
  | 'sin_evidencia';

export interface StatusBadgeProps {
  status: SemaforoStatus;
  className?: string;
}
