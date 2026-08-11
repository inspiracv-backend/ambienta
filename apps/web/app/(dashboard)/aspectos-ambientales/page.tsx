'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Spinner } from '@/components/atoms';
import { AspectosAmbientalesTable } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';
import { mockAspectosAmbientales } from '@/mocks/aspectos-ambientales';

export default function AspectosAmbientalesPage() {
  const router = useRouter();
  const { user } = useSession();
  const { tenants } = useTenants();

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

  const tenant = tenants.find((t) => t.id === user.tenantId);
  const plants = tenant?.plants ?? [];
  const aspectos = mockAspectosAmbientales.filter((a) => a.tenantId === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Aspectos Ambientales</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre} · ISO 14001 §6.1.2</p>
      </div>
      <AspectosAmbientalesTable aspectos={aspectos} plants={plants} />
    </div>
  );
}
