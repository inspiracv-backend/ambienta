'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FileWarning, ShieldAlert, Clock } from 'lucide-react';
import { MetricCounter } from '@/components/molecules';
import { DashboardHeroCard, DeadlinesList, MultiPlantTable } from '@/components/organisms';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { computePlantMetrics } from '@/lib/dashboard-metrics';
import { mockTenants } from '@/mocks/tenants';
import { mockObligations } from '@/mocks/obligations';
import { mockNonConformities } from '@/mocks/audits';

const INCUMPLIMIENTO_STATES = new Set(['vencida', 'sin_evidencia']);

/**
 * S-06 Dashboard Principal + S-07 Dashboard Multi-Instalación.
 * Fetching real: reemplazar los mocks de abajo por llamadas a apps/api
 * (GET /tenants/:id/dashboard) cuando exista spec aprobada — RF-47/RF-48.
 */
export default function DashboardPage() {
  const router = useRouter();
  const { user } = useSession();

  useEffect(() => {
    if (user === null) {
      const stillChecking = window.localStorage.getItem('ambienta.mockUserId');
      if (!stillChecking) router.replace('/login');
    }
  }, [user, router]);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const tenant = mockTenants.find((t) => t.id === user.tenantId);
  const isVistaSimplificada = user.role === 'admin_empresa';

  // Usuario Interno/Especialista ven solo sus plantas asignadas (vista densa);
  // Admin Empresa/Superadmin ven el tenant completo (vista simplificada, H7).
  const scopedPlants =
    !isVistaSimplificada && user.plantIds.length > 0
      ? (tenant?.plants ?? []).filter((p) => user.plantIds.includes(p.id))
      : tenant?.plants ?? [];

  const scopedObligations = mockObligations.filter(
    (o) => o.tenantId === user.tenantId && scopedPlants.some((p) => p.id === o.plantId),
  );

  const metrics = computePlantMetrics(scopedPlants, scopedObligations, mockNonConformities);

  const incumplimientos = scopedObligations.filter((o) => INCUMPLIMIENTO_STATES.has(o.estado)).length;
  const ncAbiertas = mockNonConformities.filter((nc) => nc.tenantId === user.tenantId && nc.estado !== 'cerrada').length;
  const porVencer = scopedObligations.filter((o) => o.estado === 'por_vencer').length;

  const proximoCritico =
    [...scopedObligations]
      .filter((o) => o.estado !== 'vigente')
      .sort((a, b) => new Date(a.proximoVencimiento).getTime() - new Date(b.proximoVencimiento).getTime())[0] ?? null;

  const cumplimientoGlobal =
    metrics.length > 0 ? metrics.reduce((sum, m) => sum + m.cumplimientoPct, 0) / metrics.length : 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          {isVistaSimplificada ? 'Resumen ejecutivo' : 'Dashboard'}
        </h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>

      <DashboardHeroCard obligation={proximoCritico} cumplimientoPct={cumplimientoGlobal} />

      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCounter label="Artículos en incumplimiento" value={incumplimientos} icon={ShieldAlert} tone="danger" />
        <MetricCounter label="No Conformidades abiertas" value={ncAbiertas} icon={FileWarning} tone="warning" />
        <MetricCounter label="Obligaciones por vencer (≤30 días)" value={porVencer} icon={Clock} tone="neutral" />
      </div>

      <section aria-labelledby="proximos-vencimientos-heading">
        <h2 id="proximos-vencimientos-heading" className="mb-3 text-sm font-semibold text-slate-700">
          Próximos vencimientos
        </h2>
        <DeadlinesList obligations={scopedObligations} />
      </section>

      {/* S-07: la tabla comparativa multi-planta es la vista ejecutiva de Admin Empresa/Superadmin
          (H7) — Usuario Interno/Especialista ya ven su detalle operativo en la lista de arriba,
          acotada a las plantas que tienen asignadas. */}
      {isVistaSimplificada && scopedPlants.length > 1 && (
        <section aria-labelledby="multi-planta-heading">
          <h2 id="multi-planta-heading" className="mb-3 text-sm font-semibold text-slate-700">
            Cumplimiento por planta
          </h2>
          <MultiPlantTable metrics={metrics} />
        </section>
      )}
    </div>
  );
}
