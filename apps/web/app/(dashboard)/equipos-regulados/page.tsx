'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Spinner } from '@/components/atoms';
import { PanelDeAtencion } from '@/components/molecules';
import { EquiposReguladosTable } from '@/components/organisms';
import { IsoProvider, useIso } from '@/lib/iso-store';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';

function Contenido() {
  const router = useRouter();
  const { user, cargando } = useSession();
  const { tenants } = useTenants();
  const {
    equipos,
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
        <Spinner label="Cargando equipos regulados" />
      </div>
    );
  }

  const tenant = tenants.find((t) => t.id === user.tenantId);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Equipos Regulados</h1>
        <p className="text-sm text-slate-500">{tenant?.nombre}</p>
      </div>
      {errorDeCarga && (
        <p role="alert" className="rounded-card bg-semaforo-no-cumple-bg px-4 py-3 text-sm text-semaforo-no-cumple">
          No se pudieron cargar los datos: {errorDeCarga}
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
        **Dos paneles y no uno**, porque son dos preguntas distintas.

        Lo que vence se resuelve con tiempo: hay que tramitar una renovación
        antes de la fecha. Un equipo sin operador habilitado **ya es un
        incumplimiento hoy**: la máquina está funcionando y quien la maneja no
        está certificado para hacerlo. Mezclarlos pondría lo urgente en la misma
        lista que lo previsible, que es la forma más rápida de que se deje de
        mirar.
      */}
      <div className="grid gap-4 lg:grid-cols-2">
        <PanelDeAtencion
          titulo="Sin operador habilitado"
          explica="Equipos en operación que hoy nadie puede operar legalmente"
          error={errorDerivadas}
          filas={derivadas?.sinOperador.map((e) => (
            <div key={e.equipmentId} className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-medium text-slate-900">{e.nombre}</span>
              {/*
                El motivo viene del servidor y **no se deduce del conteo**: son
                dos arreglos distintos —asignar a alguien, o renovar la
                certificación que caducó— y decir sólo "sin operador" mandaría a
                asignar gente donde ya la hay.
              */}
              <span className="text-slate-500">
                ·{' '}
                {e.motivo === 'sin_operador'
                  ? 'nadie asignado'
                  : `certificación vencida (${e.operadoresAsignados} asignado${
                      e.operadoresAsignados === 1 ? '' : 's'
                    })`}
              </span>
            </div>
          ))}
          vacio="Todos los equipos en operación tienen a alguien habilitado."
        />

        <PanelDeAtencion
          titulo="Por vencer"
          explica="Inscripciones del equipo y certificaciones de sus operadores"
          error={errorDerivadas}
          nota={derivadas?.diasDeAviso ? `ventana de ${derivadas.diasDeAviso} días` : undefined}
          filas={
            derivadas &&
            [...derivadas.inscripciones, ...derivadas.certificaciones]
              // Lo ya vencido primero: `diasRestantes` sale negativo y esa es
              // exactamente la fila que hay que ver antes que ninguna.
              .sort((a, b) => a.diasRestantes - b.diasRestantes)
              .map((v, i) => (
                <div key={`${v.equipmentId}-${v.userId ?? 'eq'}-${i}`} className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-medium text-slate-900">{v.nombre}</span>
                  {v.detalle && <span className="text-xs text-slate-400">{v.detalle}</span>}
                  <span
                    className={
                      v.diasRestantes < 0
                        ? 'text-semaforo-no-cumple'
                        : 'text-slate-500'
                    }
                  >
                    ·{' '}
                    {v.diasRestantes < 0
                      ? `vencida hace ${Math.abs(v.diasRestantes)} días`
                      : `vence en ${v.diasRestantes} días`}
                  </span>
                </div>
              ))
          }
          vacio="Nada por vencer en la ventana consultada."
        />
      </div>
      <EquiposReguladosTable equipos={equipos} plants={plantas} />
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
