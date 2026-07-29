'use client';

import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/atoms';
import { PageHeader } from '@/components/molecules';
import { NuevoTenantModal, TenantsManagementTable } from '@/components/organisms';
import { useTenants } from '@/lib/tenants-store';
import { useUsers } from '@/lib/users-store';

/** S-36 Gestión de Tenants (exclusivo Superadmin, ver lib/navigation.ts). */
export default function GestionTenantsPage() {
  const { tenants } = useTenants();
  const { users } = useUsers();
  const [isNuevoOpen, setIsNuevoOpen] = useState(false);

  // Se lee del store en vivo y no del mock estático: si se invita o desactiva
  // un usuario, el conteo por empresa debe reflejarlo sin recargar.
  const userCounts = tenants.reduce<Record<string, number>>((acc, t) => {
    acc[t.id] = users.filter((u) => u.tenantId === t.id).length;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Gestión de Tenants"
        descripcion="Empresas registradas en la plataforma"
        acciones={
          <Button onClick={() => setIsNuevoOpen(true)} icon={<Plus className="h-4 w-4" aria-hidden />}>
            Dar de alta empresa
          </Button>
        }
      />

      {/* Suspender vive dentro del detalle, en zona de riesgo: no es una
          acción que deba estar a un clic desde el listado. */}
      <TenantsManagementTable tenants={tenants} userCounts={userCounts} />

      <NuevoTenantModal open={isNuevoOpen} onOpenChange={setIsNuevoOpen} />
    </div>
  );
}
