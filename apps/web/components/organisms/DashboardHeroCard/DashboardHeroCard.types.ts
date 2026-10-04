import type { VencimientoResumen } from '@/lib/dashboard-metrics';

export interface DashboardHeroCardProps {
  /**
   * Resumen y no `Obligation` completa: la API de metricas devuelve agregados,
   * no entidades, y la tarjeta solo muestra nombre, fecha y semaforo.
   */
  obligation: VencimientoResumen | null;
  /** Fraccion 0-1, no porcentaje. La tarjeta lo multiplica por 100. */
  /** `null` = todavia no hay articulos evaluados. **No es cero.** */
  cumplimientoPct: number | null;
  /**
   * Fraccion 0-1 de lo que aplica que ya se evaluo. **Va al lado del
   * cumplimiento y no dentro** (ISO 14001, "cumplimiento y cobertura son
   * indicadores distintos"): un 30 % puede ser incumplimiento o falta de
   * evaluacion, y el numero solo no lo distingue. `null` o ausente = no se sabe
   * (el respaldo de ejemplo, o una API vieja): no se muestra.
   */
  cobertura?: number | null;
  /** Requisitos que aplican y siguen sin evaluar. */
  porEvaluar?: number | null;
}
