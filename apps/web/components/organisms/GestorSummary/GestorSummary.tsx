'use client';

import Link from 'next/link';
import { Briefcase, CalendarClock, FileWarning, Users2 } from 'lucide-react';
import { EmptyState, StatCard } from '@/components/molecules';
import { useGestores } from '@/lib/gestores-store';
import { computeResumenGestor, DIAS_AVISO_CONTRATO } from '@/lib/role-dashboard';

/**
 * Bloque de cartera del Gestor (A4) dentro de su dashboard.
 *
 * Para un Gestor el riesgo principal no son sus propias obligaciones sino los
 * contratos con sus clientes: el Contrato es la entidad formal de la que
 * cuelga todo el sub-tenant (RF-66), así que uno vencido significa estar
 * prestando servicio sin respaldo. Por eso el bloque abre con lo que vence,
 * no con el total de clientes.
 */
export function GestorSummary() {
  const { subTenants, contratos } = useGestores();
  const r = computeResumenGestor(subTenants, contratos);

  return (
    <section aria-labelledby="cartera-gestor" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="cartera-gestor" className="text-sm font-semibold text-slate-900">
          Mi cartera de clientes
        </h2>
        <Link
          href="/gestores"
          className="text-xs font-medium text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          Ver todos
        </Link>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          etiqueta="Clientes activos"
          valor={r.subTenantsActivos}
          detalle={r.subTenantsInactivos > 0 ? `${r.subTenantsInactivos} inactivo(s)` : 'Todos operativos'}
          icono={Users2}
          href="/gestores"
        />
        <StatCard
          etiqueta="Contratos vigentes"
          valor={r.contratosVigentes}
          detalle={`${r.contratosPorVencer.length} por vencer`}
          icono={Briefcase}
          tono={r.contratosPorVencer.length > 0 ? 'atencion' : 'positivo'}
        />
        <StatCard
          etiqueta="Contratos vencidos"
          valor={r.contratosVencidos}
          detalle={r.contratosVencidos > 0 ? 'Servicio sin respaldo formal' : 'Ninguno'}
          icono={FileWarning}
          tono={r.contratosVencidos > 0 ? 'critico' : 'positivo'}
        />
      </div>

      {r.contratosPorVencer.length > 0 ? (
        <div className="rounded-card border border-slate-200 bg-white p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <CalendarClock className="h-4 w-4 text-semaforo-parcial" aria-hidden />
            Contratos por renovar
          </p>
          <p className="mt-0.5 text-xs text-slate-500">Vencen dentro de {DIAS_AVISO_CONTRATO} días.</p>
          <ul className="mt-3 flex flex-col divide-y divide-slate-100">
            {r.contratosPorVencer.map(({ contrato, subTenant, diasRestantes }) => (
              <li key={contrato.id} className="flex items-center justify-between gap-3 py-2">
                <div className="min-w-0">
                  <Link
                    href={`/gestores/${contrato.subTenantId}/contratos`}
                    className="block truncate text-sm font-medium text-slate-800 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  >
                    {subTenant?.nombre ?? 'Cliente sin nombre'}
                  </Link>
                  <p className="truncate text-xs text-slate-500">{contrato.nombre}</p>
                </div>
                <span
                  className={
                    diasRestantes <= 7
                      ? 'shrink-0 rounded-full bg-semaforo-no-cumple-bg px-2 py-0.5 text-xs font-semibold text-semaforo-no-cumple'
                      : 'shrink-0 rounded-full bg-semaforo-parcial-bg px-2 py-0.5 text-xs font-semibold text-semaforo-parcial'
                  }
                >
                  {diasRestantes === 0 ? 'Vence hoy' : `${diasRestantes} día${diasRestantes === 1 ? '' : 's'}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <EmptyState
          icono={Briefcase}
          titulo="Sin contratos por renovar"
          descripcion={`Ningún contrato vence en los próximos ${DIAS_AVISO_CONTRATO} días.`}
        />
      )}
    </section>
  );
}
