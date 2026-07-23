import type { Obligation, Plant, NonConformity } from '@ambienta/shared';

export interface PlantMetric {
  plant: Plant;
  cumplimientoPct: number;
  incumplimientos: number;
  noConformidadesActivas: number;
  proximoVencimiento: Obligation | null;
}

const INCUMPLIMIENTO_STATES = new Set(['vencida', 'sin_evidencia']);

export function computePlantMetrics(
  plants: Plant[],
  obligations: Obligation[],
  nonConformities: NonConformity[],
): PlantMetric[] {
  return plants.map((plant) => {
    const plantObligations = obligations.filter((o) => o.plantId === plant.id);
    const incumplimientos = plantObligations.filter((o) => INCUMPLIMIENTO_STATES.has(o.estado)).length;
    const vigentes = plantObligations.filter((o) => o.estado === 'vigente').length;
    const cumplimientoPct = plantObligations.length > 0 ? vigentes / plantObligations.length : 0;

    const proximoVencimiento =
      [...plantObligations]
        .filter((o) => o.estado !== 'vigente')
        .sort((a, b) => new Date(a.proximoVencimiento).getTime() - new Date(b.proximoVencimiento).getTime())[0] ?? null;

    return {
      plant,
      cumplimientoPct,
      incumplimientos,
      noConformidadesActivas: nonConformities.filter((nc) => nc.tenantId === plant.tenantId && nc.estado !== 'cerrada').length,
      proximoVencimiento,
    };
  });
}
