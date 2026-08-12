'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { EquipoPlataformaView } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { rutaInicialParaRol } from '@/lib/navigation';

/**
 * Equipo de plataforma (RF-81, RF-84) — exclusivo del Superadmin.
 *
 * Es la contraparte de "Usuarios y Roles": esa pantalla administra a la gente
 * de una empresa, esta a la gente de Ambienta. Mantenerlas separadas evita que
 * un Admin Empresa vea siquiera que existen cuentas de plataforma.
 */
export default function EquipoPage() {
  const router = useRouter();
  const { user, cargando } = useSession();

  const esSuperadmin = user?.role === 'superadmin';

  useEffect(() => {
    if (!cargando && user === null) router.replace('/login');
    else if (user && !esSuperadmin) router.replace(rutaInicialParaRol(user.role));
  }, [cargando, user, esSuperadmin, router]);

  if (!user || !esSuperadmin) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  return <EquipoPlataformaView currentUserId={user.id} />;
}
