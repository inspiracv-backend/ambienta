'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { PageHeader } from '@/components/molecules';
import { UsersManagementTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useUsers } from '@/lib/users-store';
import { useDepartamentos } from '@/lib/departamentos-store';
import { navItemsParaRol, rutaInicialParaRol } from '@/lib/navigation';
import { useTenants } from '@/lib/tenants-store';

/**
 * S-41 Gestión de Usuarios y Roles (RF-08).
 *
 * El permiso se deriva de `lib/navigation.ts` en vez de repetir aquí la lista
 * de roles: la matriz le da este módulo al Admin Empresa y al Gestor (A4 =
 * A1 + módulo Gestores), y tener el criterio en dos lugares fue justamente lo
 * que hizo que el menú ofreciera la pantalla al Gestor mientras la página lo
 * rebotaba.
 */
export default function UsuariosPage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const { users } = useUsers();
  const { departamentos } = useDepartamentos();

  const puedeGestionarUsuarios = user
    ? navItemsParaRol(user.role).some((item) => item.href === '/usuarios')
    : false;

  useEffect(() => {
    if (!cargando && user === null) router.replace('/login');
    else if (user && !puedeGestionarUsuarios) router.replace(rutaInicialParaRol(user.role));
  }, [cargando, user, puedeGestionarUsuarios, router]);

  if (!user || !puedeGestionarUsuarios) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const tenant = tenants.find((t) => t.id === user.tenantId);
  const tenantUsers = users.filter((u) => u.tenantId === user.tenantId);
  const tenantDepartamentos = departamentos.filter((d) => d.tenantId === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader titulo="Usuarios y Roles" descripcion={tenant?.nombre} />
      <UsersManagementTable
        users={tenantUsers}
        plants={tenant?.plants ?? []}
        departamentos={tenantDepartamentos}
        tenantId={user.tenantId ?? ''}
        esGestorTenant={tenant?.esGestor ?? false}
        currentUserId={user.id}
      />
    </div>
  );
}
