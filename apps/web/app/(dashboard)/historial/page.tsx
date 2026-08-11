'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { PageHeader } from '@/components/molecules';
import { AuditLogView } from '@/components/organisms';
import { useSession } from '@/lib/session';

/**
 * Historial consolidado (RF-32, RNF-25, RNF-26).
 *
 * Es la misma pantalla para los dos ámbitos, pero el alcance lo fija el rol y
 * no un filtro que el usuario pueda cambiar: el Superadmin ve la actividad de
 * plataforma (`tenantId: null`) y los roles de tenant solo la de su empresa.
 * En el backend esa separación la impone RLS.
 */
export default function HistorialPage() {
  const router = useRouter();
  const { user, cargando } = useSession();

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

  const esSuperadmin = user.role === 'superadmin';

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Historial"
        descripcion={
          esSuperadmin
            ? 'Registro de las acciones de administración de la plataforma.'
            : 'Registro completo e inalterable de lo que ha pasado en tu empresa.'
        }
      />
      <AuditLogView tenantIdVisible={esSuperadmin ? null : user.tenantId} />
    </div>
  );
}
