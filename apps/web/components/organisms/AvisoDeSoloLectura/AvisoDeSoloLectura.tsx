'use client';

import { Lock } from 'lucide-react';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';

/**
 * Una empresa suspendida o cerrada queda en **solo lectura** (spec de RBAC,
 * decisión del 21-sep): la API rechaza toda escritura con
 * `empresa_en_solo_lectura`.
 *
 * El aviso va arriba de cada pantalla y no solo en el error de cada botón. Sin
 * él, la persona descubre el estado de a un rechazo por vez y cada uno se lee
 * como una falla distinta del sistema.
 */
export function AvisoDeSoloLectura() {
  const { user } = useSession();
  const { tenants } = useTenants();
  const tenant = tenants.find((t) => t.id === user?.tenantId);

  if (!tenant || (tenant.estado !== 'suspendido' && tenant.estado !== 'cerrado')) return null;

  return (
    <div
      role="status"
      className="mb-4 flex items-start gap-3 rounded-card border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <Lock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p>
        <strong>{tenant.estado === 'suspendido' ? 'Empresa suspendida.' : 'Empresa cerrada.'}</strong>{' '}
        Puedes consultar y exportar tu información, pero no crear ni modificar registros.
        {tenant.estado === 'suspendido' && ' Para reactivarla, contacta a Ambienta.'}
      </p>
    </div>
  );
}
