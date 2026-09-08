'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Spinner } from '@/components/atoms';
import { PanelDeAtencion } from '@/components/molecules';
import { AspectosAmbientalesTable } from '@/components/organisms';
import { IsoProvider, useIso } from '@/lib/iso-store';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';

function Contenido() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const {
    aspectos,
    plantas,
    cargando: cargandoIso,
    errorDeCarga,
    truncado,
    derivadas,
    errorDerivadas,
  } = useIso();

  useEffect(() => {
    if (!FEATURE_FLAGS.matricesIso) router.replace('/dashboard');
    if (!cargando && user === null) router.replace('/login');
  }, [cargando, user, router]);

  if (!user || cargandoIso) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando aspectos ambientales" />
      </div>
    );
  }

  const tenant = tenants.find((t) => t.id === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Aspectos Ambientales</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre} · ISO 14001 §6.1.2</p>
      </div>
      {errorDeCarga && (
        <p role="alert" className="rounded-card bg-semaforo-no-cumple-bg px-4 py-3 text-sm text-semaforo-no-cumple">
          No se pudieron cargar los aspectos: {errorDeCarga}
        </p>
      )}
      {truncado.length > 0 && (
        <p
          role="status"
          className="rounded-card border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          La lista viene <strong>cortada</strong> por el tope del servidor
          ({truncado.join(', ')}): hay más registros de los que se ven. Filtra para
          acotar la búsqueda.
        </p>
      )}
      {/*
        **La cadena que ISO exige, hecha visible.** §6.1.2 declara qué aspectos
        son significativos y §6.1.4 obliga a gestionarlos. Un aspecto
        significativo sin riesgo asociado es la matriz a medias, y es lo primero
        que pregunta una auditoría — pero mirando sólo la tabla de aspectos no
        se nota, porque la tabla no sabe nada de los riesgos.
      */}
      <PanelDeAtencion
        titulo="Significativos sin tratar"
        explica="Aspectos significativos que nadie enlazó a un riesgo u oportunidad (§6.1.4)"
        error={errorDerivadas}
        filas={derivadas?.sinTratar.map((a) => (
          <div key={a.id} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-medium text-slate-900">{a.aspecto}</span>
            <span className="text-slate-500">· {a.actividad}</span>
            {a.puntajeTotal !== null && (
              <span className="text-xs tabular-nums text-slate-400">
                puntaje {a.puntajeTotal}
              </span>
            )}
          </div>
        ))}
        vacio="Todos los aspectos significativos tienen un riesgo u oportunidad asociado."
      />
      <AspectosAmbientalesTable aspectos={aspectos} plants={plantas} />
    </div>
  );
}

export default function AspectosAmbientalesPage() {
  return (
    <IsoProvider>
      <Contenido />
    </IsoProvider>
  );
}
