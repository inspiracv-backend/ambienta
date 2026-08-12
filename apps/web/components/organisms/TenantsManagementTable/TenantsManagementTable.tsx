'use client';

import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import { diasParaVencimiento, nombreDePais } from '@ambienta/shared';
import { AccountBadge } from '@/components/atoms';
import { cn } from '@/lib/utils';
import type { TenantsManagementTableProps } from './TenantsManagementTable.types';

/**
 * S-36 Gestión de Tenants.
 *
 * **Ya no hay acciones destructivas en la fila.** Antes cada fila tenía un
 * botón rojo "Deshabilitar" a un clic de distancia. El equipo lo objetó con
 * un argumento correcto: estas no son cuentas transaccionales sino contratos
 * anuales, y suspender una empresa deja a todos sus usuarios fuera. Un
 * diálogo de confirmación no basta cuando el botón está en la misma línea que
 * el enlace para ver el detalle.
 *
 * Ahora la fila solo navega. Suspender vive dentro del detalle del tenant, en
 * una zona de riesgo separada — el patrón de GitHub y Stripe: separación
 * física, no un `confirm()` más.
 */
export function TenantsManagementTable({ tenants, userCounts }: TenantsManagementTableProps) {
  return (
    <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
      <table className="w-full min-w-[760px] text-sm">
        <caption className="sr-only">Empresas (tenants) de la plataforma</caption>
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
            <th scope="col" className="px-4 py-3">Empresa</th>
            <th scope="col" className="px-4 py-3">Estado</th>
            <th scope="col" className="px-4 py-3">Suscripción</th>
            <th scope="col" className="px-4 py-3">Usuarios</th>
            <th scope="col" className="px-4 py-3">Módulos</th>
            <th scope="col" className="px-4 py-3"><span className="sr-only">Ver detalle</span></th>
          </tr>
        </thead>
        <tbody>
          {tenants.map((t) => {
            const usuarios = userCounts[t.id] ?? 0;
            const limite = t.suscripcion.limiteUsuarios;
            const dias = diasParaVencimiento(t.suscripcion);
            const esDemo = t.suscripcion.plan === 'demo';

            return (
              <tr key={t.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link
                    href={`/gestion-tenants/${t.id}`}
                    className="font-medium text-slate-800 hover:text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  >
                    {t.nombre}
                  </Link>
                  <p className="text-xs text-slate-500">
                    {t.esGestor ? 'Gestor' : t.sector} · {nombreDePais(t.pais)} · {t.identificacion.tipo}{' '}
                    {t.identificacion.numero}
                  </p>
                </td>

                <td className="px-4 py-3">
                  {/* Estado de la cuenta, no semáforo de cumplimiento ambiental:
                      una empresa suspendida no está "en incumplimiento" normativo. */}
                  <AccountBadge estado={t.estado} />
                  {!t.perfilEmpresaCompleto && (
                    <p className="mt-1 text-[11px] font-medium text-semaforo-parcial">Perfil pendiente</p>
                  )}
                </td>

                <td className="px-4 py-3">
                  <span
                    className={cn(
                      'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
                      esDemo ? 'bg-semaforo-parcial-bg text-semaforo-parcial' : 'bg-slate-100 text-slate-600',
                    )}
                  >
                    {esDemo ? 'Demo' : 'Contrato'}
                  </span>
                  <p
                    className={cn(
                      'mt-1 text-xs',
                      dias < 0 ? 'font-semibold text-semaforo-no-cumple' : dias <= 15 ? 'font-medium text-semaforo-parcial' : 'text-slate-500',
                    )}
                  >
                    {dias < 0 ? `Venció hace ${Math.abs(dias)} d` : dias === 0 ? 'Vence hoy' : `${dias} días restantes`}
                  </p>
                </td>

                <td className="px-4 py-3 text-slate-500">
                  <span className={usuarios >= limite ? 'font-semibold text-semaforo-no-cumple' : undefined}>
                    {usuarios}
                  </span>
                  {' / '}
                  {limite}
                </td>

                <td className="px-4 py-3 text-slate-500">{t.modulosActivos.length}</td>

                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/gestion-tenants/${t.id}`}
                    aria-label={`Ver detalle de ${t.nombre}`}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  >
                    Administrar
                    <ChevronRight className="h-3.5 w-3.5" aria-hidden />
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
