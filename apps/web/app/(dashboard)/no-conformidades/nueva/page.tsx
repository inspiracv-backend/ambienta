'use client';

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { RegisterFindingForm } from '@/components/organisms';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';
import { mockUsers } from '@/mocks/users';

/**
 * S-24 Crear/Registrar Hallazgo.
 *
 * El contenido va dentro de `<Suspense>` porque usa `useSearchParams()`, que
 * en el App Router obliga a Next a renderizar del lado del cliente. Sin la
 * frontera, `next build` falla al prerenderizar esta ruta (el modo desarrollo
 * lo tolera, así que el error solo aparece al construir para producción).
 */
export default function NuevaNoConformidadPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center">
          <Spinner label="Cargando formulario" />
        </div>
      }
    >
      <NuevaNoConformidadContent />
    </Suspense>
  );
}

function NuevaNoConformidadContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useSession();
  const { tenants } = useTenants();

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
  const responsableOptions = mockUsers.filter((u) => u.tenantId === user.tenantId).map((u) => ({ id: u.id, nombre: u.nombre }));

  return (
    <div className="flex flex-col items-start gap-4">
      <Breadcrumbs items={[{ label: 'No Conformidades', href: '/no-conformidades' }, { label: 'Registrar hallazgo' }]} />
      <RegisterFindingForm
        tenantId={user.tenantId ?? ''}
        plants={tenant?.plants ?? []}
        responsableOptions={responsableOptions}
        defaultPlantId={searchParams.get('plantId') ?? undefined}
        defaultAuditId={searchParams.get('auditId') ?? undefined}
      />
    </div>
  );
}
