import type { Obligation, Plant, NonConformity } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms/StatusBadge/StatusBadge.types';

/**
 * Lo que el Dashboard necesita de una planta. No es `Plant` completo a
 * proposito: la API de metricas devuelve agregados, no entidades, y exigir un
 * `Plant` entero obligaria a inventar campos que el endpoint nunca envio.
 */
export interface PlantMetric {
  plant: Pick<Plant, 'id' | 'nombre' | 'comuna' | 'region'>;
  cumplimientoPct: number;
  incumplimientos: number;
  noConformidadesActivas: number;
  proximoVencimiento: VencimientoResumen | null;
}

/** El minimo que las tarjetas y la tabla muestran de un vencimiento. */
export interface VencimientoResumen {
  /** Para enlazar al detalle de la obligacion (RF-49). */
  id: string;
  nombre: string;
  proximoVencimiento: string;
  estado: SemaforoStatus;
  diasRestantes: number | null;
}

// --- Contrato del endpoint GET /dashboard/metrics ----------------------------
// Espejo de apps/api/app/schemas/dashboard.py. Los nombres van en snake_case
// porque son los que viajan en el JSON; la conversion ocurre en el adaptador.

export interface ApiCriticalDeadline {
  obligation_id: string;
  code: string;
  title: string;
  due_at: string | null;
  days_remaining: number | null;
  status: string;
}

export interface ApiDashboardMetrics {
  tenant_id: string;
  generated_at: string;
  global: {
    /** 0 a 100. Ojo: la UI trabaja en 0 a 1. */
    compliance_percentage: number;
    articles_evaluated: number;
    articles_non_compliant: number;
    total_obligations: number;
    nc_open: number;
    obligations_upcoming: number;
    obligations_overdue: number;
  };
  critical_deadline: ApiCriticalDeadline | null;
  facilities: {
    facility_id: string;
    name: string;
    commune_code: string | null;
    region_code: string | null;
    compliance_percentage: number;
    non_compliant_count: number;
    nc_open_count: number;
    critical_deadline: ApiCriticalDeadline | null;
  }[];
}

/**
 * La API habla en porcentaje (0-100) y los componentes en fraccion (0-1),
 * porque hacen `Math.round(pct * 100)`. Pasar el valor crudo mostraria 7530%.
 * Una sola funcion hace la conversion para que el error no se pueda repetir
 * en cada punto de uso.
 */
function aFraccion(porcentaje: number): number {
  return porcentaje / 100;
}

/**
 * `obligations.status` de la API al semaforo de la UI.
 *
 * Son dos vocabularios distintos: la API describe el ciclo de vida del tramite
 * y el semaforo describe urgencia. `vencida` no sale del status sino de la
 * fecha, asi que se decide con los dias restantes.
 */
function aSemaforo(status: string, diasRestantes: number | null): SemaforoStatus {
  if (diasRestantes !== null && diasRestantes < 0) return 'vencida';
  if (status === 'draft') return 'sin_evidencia';
  if (diasRestantes !== null && diasRestantes <= 30) return 'por_vencer';
  return 'vigente';
}

function aVencimiento(d: ApiCriticalDeadline | null): VencimientoResumen | null {
  if (!d || !d.due_at) return null;
  return {
    id: d.obligation_id,
    nombre: d.title,
    proximoVencimiento: d.due_at,
    estado: aSemaforo(d.status, d.days_remaining),
    diasRestantes: d.days_remaining,
  };
}

/** Respuesta de la API al modelo de vista que consumen los componentes. */
export function fromApiMetrics(api: ApiDashboardMetrics) {
  return {
    cumplimientoGlobal: aFraccion(api.global.compliance_percentage),
    incumplimientos: api.global.articles_non_compliant,
    ncAbiertas: api.global.nc_open,
    porVencer: api.global.obligations_upcoming,
    vencidas: api.global.obligations_overdue,
    proximoCritico: aVencimiento(api.critical_deadline),
    plantas: api.facilities.map(
      (f): PlantMetric => ({
        plant: {
          id: f.facility_id,
          nombre: f.name,
          comuna: f.commune_code ?? '',
          region: f.region_code ?? '',
        },
        cumplimientoPct: aFraccion(f.compliance_percentage),
        incumplimientos: f.non_compliant_count,
        noConformidadesActivas: f.nc_open_count,
        proximoVencimiento: aVencimiento(f.critical_deadline),
      }),
    ),
  };
}

export type DashboardViewModel = ReturnType<typeof fromApiMetrics>;

const INCUMPLIMIENTO_STATES = new Set(['vencida', 'sin_evidencia']);

/**
 * Calculo local sobre mocks. Se conserva como respaldo para cuando la API no
 * responde: el Dashboard sigue mostrando algo en vez de quedar en blanco.
 */
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

    const proxima =
      [...plantObligations]
        .filter((o) => o.estado !== 'vigente')
        .sort((a, b) => new Date(a.proximoVencimiento).getTime() - new Date(b.proximoVencimiento).getTime())[0] ?? null;

    return {
      plant: {
        id: plant.id,
        nombre: plant.nombre,
        comuna: plant.comuna,
        region: plant.region,
      },
      cumplimientoPct,
      incumplimientos,
      noConformidadesActivas: nonConformities.filter(
        (nc) => nc.tenantId === plant.tenantId && nc.estado !== 'cerrada',
      ).length,
      proximoVencimiento: proxima
        ? {
            id: proxima.id,
            nombre: proxima.nombre,
            proximoVencimiento: proxima.proximoVencimiento,
            estado: proxima.estado,
            diasRestantes: null,
          }
        : null,
    };
  });
}
