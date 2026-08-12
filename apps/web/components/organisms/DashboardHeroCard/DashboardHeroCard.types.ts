import type { VencimientoResumen } from '@/lib/dashboard-metrics';

export interface DashboardHeroCardProps {
  /**
   * Resumen y no `Obligation` completa: la API de metricas devuelve agregados,
   * no entidades, y la tarjeta solo muestra nombre, fecha y semaforo.
   */
  obligation: VencimientoResumen | null;
  /** Fraccion 0-1, no porcentaje. La tarjeta lo multiplica por 100. */
  cumplimientoPct: number;
}
