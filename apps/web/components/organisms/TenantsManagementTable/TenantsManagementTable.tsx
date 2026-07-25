'use client';

import { useState } from 'react';
import Link from 'next/link';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, X } from 'lucide-react';
import type { Tenant } from '@ambienta/shared';
import { StatusBadge, Button } from '@/components/atoms';
import { tenantSemaforo } from '@/lib/tenant-status';
import type { TenantsManagementTableProps } from './TenantsManagementTable.types';

/**
 * S-36 Gestión de Tenants: habilitar/deshabilitar, editar límites (RF-59).
 * Deshabilitar pide confirmación explícita (H5) por su impacto en usuarios
 * reales de ese tenant; habilitar es reversible y de bajo riesgo, no la pide.
 */
export function TenantsManagementTable({ tenants, userCounts, onToggleEstado }: TenantsManagementTableProps) {
  const [pendingDisable, setPendingDisable] = useState<Tenant | null>(null);

  return (
    <>
      <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
        <table className="w-full min-w-[720px] text-sm">
          <caption className="sr-only">Empresas (tenants) de la plataforma</caption>
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
              <th scope="col" className="px-4 py-3">Empresa</th>
              <th scope="col" className="px-4 py-3">Estado</th>
              <th scope="col" className="px-4 py-3">Usuarios</th>
              <th scope="col" className="px-4 py-3">Módulos habilitados</th>
              <th scope="col" className="px-4 py-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">
                  <Link href={`/gestion-tenants/${t.id}`} className="hover:underline">
                    {t.nombre}
                  </Link>
                  <p className="text-xs font-normal text-slate-500">{t.esGestor ? 'Gestor' : t.sector}</p>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={tenantSemaforo(t.estado)} />
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {userCounts[t.id] ?? 0} / {t.limiteUsuarios}
                </td>
                <td className="px-4 py-3 text-slate-500">{t.modulosActivos.length}</td>
                <td className="px-4 py-3">
                  <Button
                    variant={t.estado === 'activo' ? 'danger' : 'secondary'}
                    size="md"
                    onClick={() => (t.estado === 'activo' ? setPendingDisable(t) : onToggleEstado(t))}
                  >
                    {t.estado === 'activo' ? 'Deshabilitar' : 'Habilitar'}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog.Root open={!!pendingDisable} onOpenChange={(open) => !open && setPendingDisable(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2 text-semaforo-no-cumple">
                <AlertTriangle className="h-5 w-5" aria-hidden />
                <Dialog.Title className="text-lg font-semibold text-slate-900">Deshabilitar tenant</Dialog.Title>
              </div>
              <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
                <X className="h-5 w-5" aria-hidden />
              </Dialog.Close>
            </div>
            <Dialog.Description className="mt-2 text-sm text-slate-600">
              Los usuarios de <strong>{pendingDisable?.nombre}</strong> perderán acceso a la plataforma de inmediato. ¿Confirmas esta acción?
            </Dialog.Description>
            <div className="mt-6 flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button variant="secondary">Cancelar</Button>
              </Dialog.Close>
              <Button
                variant="danger"
                onClick={() => {
                  if (pendingDisable) onToggleEstado(pendingDisable);
                  setPendingDisable(null);
                }}
              >
                Sí, deshabilitar
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
