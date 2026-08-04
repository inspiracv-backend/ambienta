'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Spinner } from '@/components/atoms';
import { EquiposReguladosTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { mockTenants } from '@/mocks/tenants';
import { mockEquiposRegulados } from '@/mocks/riesgos-oportunidades';

export default function EquiposReguladosPage() {
  const router = useRouter();
  const { user } = useSession();

  useEffect(() => {
    if (!FEATURE_FLAGS.matricesIso) router.replace('/dashboard');
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
  const plants = tenant?.plants ?? [];
  const equipos = mockEquiposRegulados.filter((e) => e.tenantId === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Equipos Regulados</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>
      <EquiposReguladosTable equipos={equipos} plants={plants} />
    </div>
  );
}
