'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { RegisterFindingForm } from '@/components/organisms';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { mockTenants } from '@/mocks/tenants';
import { mockUsers } from '@/mocks/users';

/** S-24 Crear/Registrar Hallazgo. */
export default function NuevaNoConformidadPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useSession();

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

  const tenant = mockTenants.find((t) => t.id === user.tenantId);
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
