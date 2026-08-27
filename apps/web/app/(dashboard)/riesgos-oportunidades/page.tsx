'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Spinner } from '@/components/atoms';
import { RiesgosOportunidadesTable } from '@/components/organisms';
import { IsoProvider, useIso } from '@/lib/iso-store';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';

function Contenido() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const { riesgos, plantas, cargando: cargandoIso, error } = useIso();

  useEffect(() => {
    if (!FEATURE_FLAGS.matricesIso) router.replace('/dashboard');
    if (!cargando && user === null) router.replace('/login');
  }, [cargando, user, router]);

  if (!user || cargandoIso) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando riesgos y oportunidades" />
      </div>
    );
  }

  const tenant = tenants.find((t) => t.id === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Riesgos y Oportunidades</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre} · ISO 14001 §6.1.4</p>
      </div>
      {error && (
        <p role="alert" className="rounded-card bg-semaforo-no-cumple-bg px-4 py-3 text-sm text-semaforo-no-cumple">
          No se pudieron cargar los datos: {error}
        </p>
      )}
      <RiesgosOportunidadesTable riesgos={riesgos} plants={plantas} />
    </div>
  );
}

export default function Pagina() {
  return (
    <IsoProvider>
      <Contenido />
    </IsoProvider>
  );
}
