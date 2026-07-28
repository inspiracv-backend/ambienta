'use client';

import Link from 'next/link';
import { AlertTriangle, Building2, LifeBuoy, ServerCog, UserCheck, Users } from 'lucide-react';
import { EmptyState, PageHeader, StatCard } from '@/components/molecules';
import { useTenants } from '@/lib/tenants-store';
import { useUsers } from '@/lib/users-store';
import { useSupportTickets } from '@/lib/support-tickets-store';
import { computePlatformMetrics } from '@/lib/platform-metrics';

/**
 * Dashboard consolidado del Superadmin (A0).
 *
 * La matriz de permisos le asigna "Dashboard consolidado: C (global)", pero
 * aterrizaba directo en la tabla de tenants: podía ver la lista, no el estado
 * de su negocio. El dashboard del tenant no le sirve porque filtra por
 * `tenantId` y el suyo es null.
 *
 * El orden de la pantalla sigue la urgencia real: primero lo que requiere
 * acción (perfiles bloqueados, tenants por chocar con su límite), después las
 * cifras de contexto. Un dashboard que abre con cifras bonitas y esconde los
 * problemas obliga a buscarlos.
 */
export function PlatformDashboard() {
  const { tenants } = useTenants();
  const { users } = useUsers();
  const { tickets } = useSupportTickets();

  const m = computePlatformMetrics(tenants, users, tickets);
  const hayPendientes = m.perfilesIncompletos.length > 0 || m.cercaDelLimite.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Plataforma"
        descripcion="Estado consolidado de Ambienta: empresas, usuarios y soporte."
      />

      <section aria-labelledby="metricas-plataforma">
        <h2 id="metricas-plataforma" className="sr-only">
          Métricas generales
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            etiqueta="Empresas activas"
            valor={m.tenantsActivos}
            detalle={m.tenantsSuspendidos > 0 ? `${m.tenantsSuspendidos} suspendida(s)` : `de ${m.tenantsTotal} registradas`}
            icono={Building2}
            tono={m.tenantsSuspendidos > 0 ? 'atencion' : 'positivo'}
            href="/gestion-tenants"
          />
          <StatCard
            etiqueta="Usuarios en clientes"
            valor={m.usuariosTotal}
            detalle="Sin contar cuentas de plataforma"
            icono={Users}
          />
          <StatCard
            etiqueta="Gestores"
            valor={m.gestores}
            detalle="Empresas con sub-tenants"
            icono={ServerCog}
          />
          <StatCard
            etiqueta="Tickets abiertos"
            valor={m.ticketsAbiertos}
            detalle={m.ticketsEnProgreso > 0 ? `${m.ticketsEnProgreso} en progreso` : 'Sin tickets en progreso'}
            icono={LifeBuoy}
            tono={m.ticketsAbiertos > 0 ? 'atencion' : 'positivo'}
            href="/soporte"
          />
        </div>
      </section>

      <section aria-labelledby="requiere-atencion" className="flex flex-col gap-3">
        <h2 id="requiere-atencion" className="text-sm font-semibold text-slate-900">
          Requiere tu atención
        </h2>

        {!hayPendientes && (
          <EmptyState
            icono={UserCheck}
            titulo="Todo en orden"
            descripcion="Ninguna empresa está bloqueada por configuración ni cerca de su límite de usuarios."
          />
        )}

        {m.perfilesIncompletos.length > 0 && (
          <div className="rounded-card border border-semaforo-parcial/30 bg-semaforo-parcial-bg p-4">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-semaforo-parcial" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-900">
                  {m.perfilesIncompletos.length} empresa(s) sin Perfil Empresa
                </p>
                <p className="mt-0.5 text-xs text-slate-600">
                  No pueden usar Matriz Legal ni Obligaciones hasta completarlo (RF-10). Suele ser la causa de un
                  cliente que no está operando después del onboarding.
                </p>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {m.perfilesIncompletos.map((t) => (
                    <li key={t.id}>
                      <Link
                        href={`/gestion-tenants/${t.id}`}
                        className="inline-flex rounded-md bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                      >
                        {t.nombre}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {m.cercaDelLimite.length > 0 && (
          <div className="rounded-card border border-slate-200 bg-white p-4">
            <p className="text-sm font-semibold text-slate-900">Cerca del límite de usuarios</p>
            <p className="mt-0.5 text-xs text-slate-500">
              Ajusta el límite antes de que el cliente choque con el tope (RF-81).
            </p>
            <ul className="mt-3 flex flex-col divide-y divide-slate-100">
              {m.cercaDelLimite.map(({ tenant, usuarios, porcentaje }) => (
                <li key={tenant.id} className="flex items-center justify-between gap-3 py-2">
                  <Link
                    href={`/gestion-tenants/${tenant.id}`}
                    className="truncate text-sm font-medium text-slate-700 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  >
                    {tenant.nombre}
                  </Link>
                  <span
                    className={
                      porcentaje >= 1
                        ? 'shrink-0 rounded-full bg-semaforo-no-cumple-bg px-2 py-0.5 text-xs font-semibold text-semaforo-no-cumple'
                        : 'shrink-0 rounded-full bg-semaforo-parcial-bg px-2 py-0.5 text-xs font-semibold text-semaforo-parcial'
                    }
                  >
                    {usuarios} / {tenant.limiteUsuarios} usuarios
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
