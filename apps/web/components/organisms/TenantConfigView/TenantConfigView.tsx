'use client';

import { useState } from 'react';
import { MODULOS_PLATAFORMA, type ModuloPlataforma } from '@ambienta/shared';
import { AccountBadge, Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useTenants } from '@/lib/tenants-store';
import { MODULO_LABEL } from '@/lib/tenant-status';
import type { TenantConfigViewProps } from './TenantConfigView.types';

/**
 * S-37 Detalle/Configuración de Tenant. Solo campos de administración de
 * plataforma son editables (límite de usuarios, módulos activos) — la
 * información básica (nombre, RUT, sector, plantas) es de solo lectura:
 * Superadmin no edita contenido de tenants (regla no negociable, CLAUDE.md).
 */
export function TenantConfigView({ tenant: tenantProp, userCount }: TenantConfigViewProps) {
  const { tenants, setLimiteUsuarios, setModulosActivos } = useTenants();
  const tenant = tenants.find((t) => t.id === tenantProp.id) ?? tenantProp;

  const [limite, setLimite] = useState(tenant.limiteUsuarios);
  const [modulos, setModulos] = useState<Set<ModuloPlataforma>>(new Set(tenant.modulosActivos));
  const [saved, setSaved] = useState(false);

  function toggleModulo(m: ModuloPlataforma) {
    setModulos((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m);
      else next.add(m);
      return next;
    });
    setSaved(false);
  }

  function handleGuardar() {
    setLimiteUsuarios(tenant.id, limite);
    setModulosActivos(tenant.id, Array.from(modulos));
    setSaved(true);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Información básica (solo lectura)</span>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">{tenant.nombre}</h1>
            <p className="mt-1 text-sm text-slate-500">
              RUT {tenant.rut} · {tenant.esGestor ? 'Gestor' : tenant.sector} · {tenant.plants.length} planta(s) · {userCount} usuario(s)
            </p>
          </div>
          <AccountBadge estado={tenant.estado} />
        </div>
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Límite de usuarios</h2>
        <FormField label="Máximo de usuarios permitidos" htmlFor="limite-usuarios">
          <Input
            id="limite-usuarios"
            type="number"
            min={userCount}
            value={limite}
            onChange={(e) => { setLimite(Number(e.target.value)); setSaved(false); }}
            className="max-w-[160px]"
          />
        </FormField>
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Módulos activos</h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {MODULOS_PLATAFORMA.map((m) => (
            <label key={m} className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={modulos.has(m)} onChange={() => toggleModulo(m)} className="h-4 w-4" />
              {MODULO_LABEL[m]}
            </label>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={handleGuardar}>Guardar configuración</Button>
        {saved && <span className="text-sm text-semaforo-cumple">Guardado.</span>}
      </div>
    </div>
  );
}
