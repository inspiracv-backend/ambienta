import type { VencimientoResumen } from '@/lib/dashboard-metrics';

export interface DeadlineListItemProps {
  /**
   * Resumen y no `Obligation`: el Dashboard recibe agregados de la API, no
   * entidades. `codigo` ocupa el lugar que antes tenia `sistema`.
   */
  obligation: VencimientoResumen;
}
