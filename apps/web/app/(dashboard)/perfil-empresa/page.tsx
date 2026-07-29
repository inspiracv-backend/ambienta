'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { PerfilEmpresaWizard } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';
import { useDepartamentos } from '@/lib/departamentos-store';
import { useUsers } from '@/lib/users-store';

/** RF-10 a RF-12 (v1.7): flujo obligatorio de Perfil Empresa del Admin Empresa. */
export default function PerfilEmpresaPage() {
  const router = useRouter();
  const { user } = useSession();
  const { tenants, updateDatosBasicos, updateLogo, addPlant, completarPerfilEmpresa } = useTenants();
  const { departamentos, addDepartamento } = useDepartamentos();
  const { users } = useUsers();

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

  // Del store en vivo, no del mock estático: al asignar un responsable de
  // proceso el mapa debe reflejarlo sin recargar.
  const usuariosTenant = users.filter((u) => u.tenantId === tenant.id);

  return (
    <PerfilEmpresaWizard
      tenant={tenant}
      departamentos={departamentos}
      usuarios={usuariosTenant}
      onUpdateDatosBasicos={(datos) => updateDatosBasicos(tenant.id, datos)}
      onUpdateLogo={(logoUrl) => updateLogo(tenant.id, logoUrl)}
      onAddPlant={(input) => addPlant(tenant.id, input)}
      onAddDepartamento={(input) => addDepartamento({ tenantId: tenant.id, ...input })}
      onCompletar={() => {
        completarPerfilEmpresa(tenant.id);
        router.push('/dashboard');
      }}
    />
  );
}
