'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { ClaveLocalCard, UserProfileView } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useUsers } from '@/lib/users-store';
import { useTenants } from '@/lib/tenants-store';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

/** S-42 Perfil de Usuario (todos los roles). */
export default function PerfilPage() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const { updateNombre } = useUsers();

  useEffect(() => {
    if (!cargando && user === null) router.replace('/login');
  }, [cargando, user, router]);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const tenant = tenants.find((t) => t.id === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <UserProfileView
        user={user}
        tenantNombre={tenant?.nombre ?? 'Sin empresa (invitado)'}
        onUpdateNombre={(nombre) => updateNombre(user.id, nombre)}
      />
      {/*
        Solo con Clerk activo. Sin él la clave la guardaría… nadie: el endpoint
        responde 503 porque no hay proveedor con el cual fijarla. Mostrar el
        formulario igual sería ofrecer algo que no puede funcionar.
      */}
      {CLERK_HABILITADO && <ClaveLocalCard />}
    </div>
  );
}
