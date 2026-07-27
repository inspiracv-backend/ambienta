'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { UsersManagementTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useUsers } from '@/lib/users-store';
import { useDepartamentos } from '@/lib/departamentos-store';
import { mockTenants } from '@/mocks/tenants';

/** S-41 Gestión de Usuarios y Roles (exclusivo Admin Empresa, RF-08). */
export default function UsuariosPage() {
  const router = useRouter();
  const { user } = useSession();
  const { users } = useUsers();
  const { departamentos } = useDepartamentos();

  useEffect(() => {
    if (user === null && !window.localStorage.getItem('ambienta.mockUserId')) router.replace('/login');
    else if (user && user.role !== 'admin_empresa') router.replace('/dashboard');
  }, [user, router]);

  if (!user || user.role !== 'admin_empresa') {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const tenant = mockTenants.find((t) => t.id === user.tenantId);
  const tenantUsers = users.filter((u) => u.tenantId === user.tenantId);
  const tenantDepartamentos = departamentos.filter((d) => d.tenantId === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Usuarios y Roles</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>
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
