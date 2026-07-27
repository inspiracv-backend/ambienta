'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { PerfilEmpresaWizard } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';
import { useDepartamentos } from '@/lib/departamentos-store';
import { mockUsers } from '@/mocks/users';

/** RF-10 a RF-12 (v1.7): flujo obligatorio de Perfil Empresa del Admin Empresa. */
export default function PerfilEmpresaPage() {
  const router = useRouter();
  const { user } = useSession();
  const { tenants, updateDatosBasicos, addPlant, completarPerfilEmpresa } = useTenants();
  const { departamentos, addDepartamento } = useDepartamentos();

  useEffect(() => {
    if (user === null && !window.localStorage.getItem('ambienta.mockUserId')) router.replace('/login');
  }, [user, router]);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const tenant = tenants.find((t) => t.id === user.tenantId);
  if (!tenant) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando empresa" />
      </div>
    );
  }

  const usuariosTenant = mockUsers.filter((u) => u.tenantId === tenant.id);

  return (
    <PerfilEmpresaWizard
      tenant={tenant}
      departamentos={departamentos}
      usuarios={usuariosTenant}
      onUpdateDatosBasicos={(datos) => updateDatosBasicos(tenant.id, datos)}
      onAddPlant={(input) => addPlant(tenant.id, input)}
      onAddDepartamento={(nombre) => addDepartamento(tenant.id, nombre)}
      onCompletar={() => {
        completarPerfilEmpresa(tenant.id);
        router.push('/dashboard');
      }}
    />
  );
}
