'use client';

import { PageHeader } from '@/components/molecules';
import { TenantsManagementTable } from '@/components/organisms';
import { useTenants } from '@/lib/tenants-store';
import { useToast } from '@/lib/toast-store';
import { useUsers } from '@/lib/users-store';

/** S-36 Gestión de Tenants (exclusivo Superadmin, ver lib/navigation.ts). */
export default function GestionTenantsPage() {
  const { tenants, setEstado } = useTenants();
  const { users } = useUsers();
  const { mostrarToast } = useToast();

  // Se lee del store en vivo y no del mock estático: si se invita o desactiva
  // un usuario, el conteo por empresa debe reflejarlo sin recargar.
  const userCounts = tenants.reduce<Record<string, number>>((acc, t) => {
    acc[t.id] = users.filter((u) => u.tenantId === t.id).length;
    return acc;
  }, {});

  function handleToggleEstado(tenantId: string, nombre: string, estadoActual: 'activo' | 'suspendido') {
    const nuevoEstado = estadoActual === 'activo' ? 'suspendido' : 'activo';
    setEstado(tenantId, nuevoEstado);

    // Suspender una empresa deja a todos sus usuarios fuera: confirmar qué
    // pasó y ofrecer revertirlo en el momento (H1 y H3). La fila cambia de
    // estado, pero en una tabla larga ese cambio puede quedar fuera de vista.
    mostrarToast({
      tipo: nuevoEstado === 'suspendido' ? 'info' : 'exito',
      mensaje: nuevoEstado === 'suspendido' ? `${nombre} fue suspendida` : `${nombre} fue reactivada`,
      descripcion:
        nuevoEstado === 'suspendido'
          ? 'Sus usuarios no podrán ingresar hasta reactivarla.'
          : 'Sus usuarios pueden volver a ingresar.',
      onUndo: () => setEstado(tenantId, estadoActual),
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader titulo="Gestión de Tenants" descripcion="Empresas registradas en la plataforma" />
      <TenantsManagementTable
        tenants={tenants}
        userCounts={userCounts}
        onToggleEstado={(tenant) => handleToggleEstado(tenant.id, tenant.nombre, tenant.estado)}
      />
    </div>
  );
}
