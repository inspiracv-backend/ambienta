'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { UserProfileView } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useUsers } from '@/lib/users-store';
import { useTenants } from '@/lib/tenants-store';

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
    <UserProfileView
      user={user}
      tenantNombre={tenant?.nombre ?? 'Sin empresa (invitado)'}
      onUpdateNombre={(nombre) => updateNombre(user.id, nombre)}
    />
  );
}
