'use client';

import { TenantsManagementTable } from '@/components/organisms';
import { useTenants } from '@/lib/tenants-store';
import { mockUsers } from '@/mocks/users';

/** S-36 Gestión de Tenants (exclusivo Superadmin, ver AppSidebar). */
export default function GestionTenantsPage() {
  const { tenants, setEstado } = useTenants();

  const userCounts = tenants.reduce<Record<string, number>>((acc, t) => {
    acc[t.id] = mockUsers.filter((u) => u.tenantId === t.id).length;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Gestión de Tenants</h1>
        <p className="text-sm text-slate-500">Empresas registradas en la plataforma</p>
      </div>
      <TenantsManagementTable
        tenants={tenants}
        userCounts={userCounts}
        onToggleEstado={(tenant) => setEstado(tenant.id, tenant.estado === 'activo' ? 'suspendido' : 'activo')}
      />
    </div>
  );
}
