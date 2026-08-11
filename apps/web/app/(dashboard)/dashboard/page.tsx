'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileWarning, ShieldAlert, Clock, RefreshCw, WifiOff } from 'lucide-react';
import { MetricCounter, PageHeader } from '@/components/molecules';
import {
  DashboardHeroCard,
  DeadlinesList,
  GestorSummary,
  MisTareasSummary,
  MultiPlantTable,
} from '@/components/organisms';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { api } from '@/lib/api-client';
import {
  computePlantMetrics,
  fromApiMetrics,
  type ApiDashboardMetrics,
  type DashboardViewModel,
} from '@/lib/dashboard-metrics';
import { useTenants } from '@/lib/tenants-store';
import { mockObligations } from '@/mocks/obligations';
import { mockNonConformities } from '@/mocks/audits';

/**
 * S-06 Dashboard Principal + S-07 Dashboard Multi-Instalación.
 *
 * Las métricas vienen de `GET /dashboard/metrics`, que las agrega en la base
 * (RF-47 a RF-49). Si la API no responde se cae a los mocks: el tablero sigue
 * mostrando algo y avisa que el dato no es real, en vez de quedar en blanco.
 */
export default function DashboardPage() {
  const router = useRouter();
  const { user } = useSession();
  const { tenants } = useTenants();

  const [metrics, setMetrics] = useState<DashboardViewModel | null>(null);
  const [cargando, setCargando] = useState(true);
  const [sinConexion, setSinConexion] = useState(false);
  const [reintento, setReintento] = useState(0);

  useEffect(() => {
    if (user === null) {
      const stillChecking = window.localStorage.getItem('ambienta.mockUserId');
      if (!stillChecking) router.replace('/login');
    }
  }, [user, router]);

  useEffect(() => {
    if (!user?.tenantId) return;

    const abort = new AbortController();
    setCargando(true);
    setSinConexion(false);

    api
      .get<ApiDashboardMetrics>('/dashboard/metrics', {
        tenantId: user.tenantId,
        signal: abort.signal,
      })
      .then((data) => setMetrics(fromApiMetrics(data)))
      .catch((err: unknown) => {
        // Cancelar al desmontar no es un fallo: sin esto, salir de la pantalla
        // durante la carga pintaba el banner de error.
        if (abort.signal.aborted) return;
        console.error('No se pudieron cargar las métricas del Dashboard', err);
        setSinConexion(true);
      })
      .finally(() => {
        if (!abort.signal.aborted) setCargando(false);
      });

    return () => abort.abort();
  }, [user?.tenantId, reintento]);

  const recargar = useCallback(() => setReintento((n) => n + 1), []);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const tenant = tenants.find((t) => t.id === user.tenantId);
  // El Gestor es A1 + módulo Gestores: le corresponde la misma vista ejecutiva
  // que al Admin Empresa, más su bloque de cartera.
  const isVistaSimplificada = user.role === 'admin_empresa' || user.role === 'gestor';
  const esUsuarioInterno = user.role === 'usuario_interno';

  // Respaldo cuando la API no responde. Usuario Interno ve solo sus plantas
  // asignadas (vista densa); Admin Empresa y Gestor ven el tenant completo (H7).
  const scopedPlants =
    !isVistaSimplificada && user.plantIds.length > 0
      ? (tenant?.plants ?? []).filter((p) => user.plantIds.includes(p.id))
      : tenant?.plants ?? [];

  const scopedObligations = mockObligations.filter(
    (o) => o.tenantId === user.tenantId && scopedPlants.some((p) => p.id === o.plantId),
  );

  const respaldo = {
    plantas: computePlantMetrics(scopedPlants, scopedObligations, mockNonConformities),
    incumplimientos: scopedObligations.filter(
      (o) => o.estado === 'vencida' || o.estado === 'sin_evidencia',
    ).length,
    ncAbiertas: mockNonConformities.filter(
      (nc) => nc.tenantId === user.tenantId && nc.estado !== 'cerrada',
    ).length,
    porVencer: scopedObligations.filter((o) => o.estado === 'por_vencer').length,
  };

  const plantas = metrics?.plantas ?? respaldo.plantas;
  const cumplimientoGlobal =
    metrics?.cumplimientoGlobal ??
    (respaldo.plantas.length > 0
      ? respaldo.plantas.reduce((sum, m) => sum + m.cumplimientoPct, 0) / respaldo.plantas.length
      : 0);

  const proximoCritico =
    metrics?.proximoCritico ??
    respaldo.plantas.map((p) => p.proximoVencimiento).filter((v) => v !== null)[0] ??
    null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo={isVistaSimplificada ? 'Resumen ejecutivo' : 'Mi trabajo'}
        descripcion={tenant?.nombre}
      />

      {sinConexion && (
        <div
          role="status"
          className="flex items-center justify-between gap-4 rounded-card border border-amber-200 bg-amber-50 px-4 py-3"
        >
          <span className="flex items-center gap-2 text-sm text-amber-800">
            <WifiOff className="h-4 w-4 shrink-0" aria-hidden />
            No pudimos conectar con el servidor. Estos números son de ejemplo, no
            reflejan tu empresa.
          </span>
          <button
            type="button"
            onClick={recargar}
            className="flex shrink-0 items-center gap-1.5 rounded-md border border-amber-300 px-3 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-100"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
            Reintentar
          </button>
        </div>
      )}

      {/* El Usuario Interno abre con lo que le toca a él (RF-40). */}
      {esUsuarioInterno && <MisTareasSummary user={user} />}

      {cargando && !metrics ? (
        <DashboardSkeleton />
      ) : (
        <>
          <DashboardHeroCard obligation={proximoCritico} cumplimientoPct={cumplimientoGlobal} />

          <div className="grid gap-4 sm:grid-cols-3">
            <MetricCounter
              label="Artículos en incumplimiento"
              value={metrics?.incumplimientos ?? respaldo.incumplimientos}
              icon={ShieldAlert}
              tone="danger"
            />
            <MetricCounter
              label="No Conformidades abiertas"
              value={metrics?.ncAbiertas ?? respaldo.ncAbiertas}
              icon={FileWarning}
              tone="warning"
            />
            <MetricCounter
              label="Obligaciones por vencer (≤30 días)"
              value={metrics?.porVencer ?? respaldo.porVencer}
              icon={Clock}
              tone="neutral"
            />
          </div>
        </>
      )}

      {/* Cartera de clientes del Gestor (A4, RF-64 a RF-66). */}
      {user.role === 'gestor' && <GestorSummary />}

      <section aria-labelledby="proximos-vencimientos-heading">
        <h2 id="proximos-vencimientos-heading" className="mb-3 text-sm font-semibold text-slate-700">
          Próximos vencimientos
        </h2>
        {/* La API devuelve la obligacion mas urgente de cada planta, que es lo
            que corresponde listar aca. Sin esto el hero decia "SIDREP vencida"
            y esta lista, justo debajo, "no hay vencimientos proximos". */}
        <DeadlinesList
          obligations={
            metrics?.proximos ??
            respaldo.plantas
              .map((p) => p.proximoVencimiento)
              .filter((v): v is NonNullable<typeof v> => v !== null)
          }
        />
      </section>

      {/* S-07: la tabla comparativa es la vista ejecutiva de Admin Empresa (H7) —
          Usuario Interno ya ve su detalle operativo en la lista de arriba. */}
      {isVistaSimplificada && plantas.length > 1 && (
        <section aria-labelledby="multi-planta-heading">
          <h2 id="multi-planta-heading" className="mb-3 text-sm font-semibold text-slate-700">
            Cumplimiento por planta
          </h2>
          <MultiPlantTable metrics={plantas} />
        </section>
      )}
    </div>
  );
}

/** Mantiene la altura de la tarjeta hero y los contadores para que no salte el layout. */
function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Cargando métricas">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-[132px] animate-pulse rounded-card bg-slate-100" />
        <div className="h-[132px] animate-pulse rounded-card bg-slate-100" />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="h-[92px] animate-pulse rounded-card bg-slate-100" />
        <div className="h-[92px] animate-pulse rounded-card bg-slate-100" />
        <div className="h-[92px] animate-pulse rounded-card bg-slate-100" />
      </div>
    </div>
  );
}
