'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, ExternalLink, FileWarning, RefreshCw } from 'lucide-react';
import { Button, Spinner, StatusBadge } from '@/components/atoms';
import { useSession } from '@/lib/session';
import {
  VACIO,
  cargarIncumplimientos,
  type Incumplimientos,
} from '@/lib/incumplimientos';
import { mensajeDeError } from '@/lib/api-client';

/**
 * S-07b — qué se está incumpliendo, con su evidencia (#126, RF-56).
 *
 * El detalle detrás del número del tablero. Sin esta pantalla, un
 * "3 incumplimientos" en el Dashboard obliga a abrir norma por norma para
 * descubrir cuáles son.
 *
 * ## Lo que ordena la pantalla es la evidencia, no la severidad
 *
 * Un incumplimiento **con** evidencia está documentado: hay un informe, una
 * medición, algo que mostrar sobre por qué no se cumple y qué se está haciendo.
 * Uno **sin** evidencia deja a la empresa sin nada que decir cuando llega una
 * fiscalización.
 *
 * Los dos son incumplimientos y ninguno se esconde, pero el segundo encabeza la
 * lista y tiene su propio contador arriba.
 */
export default function IncumplimientosPage() {
  const { user, cargando: cargandoSesion } = useSession();
  const [datos, setDatos] = useState<Incumplimientos>(VACIO);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reintento, setReintento] = useState(0);

  useEffect(() => {
    if (!user?.tenantId) {
      if (!cargandoSesion) setCargando(false);
      return;
    }
    const abort = new AbortController();
    setCargando(true);
    setError(null);

    cargarIncumplimientos(user.tenantId)
      .then((d) => {
        if (!abort.signal.aborted) setDatos(d);
      })
      .catch((e: unknown) => {
        // Cancelar al desmontar no es un fallo.
        if (!abort.signal.aborted) setError(mensajeDeError(e));
      })
      .finally(() => {
        if (!abort.signal.aborted) setCargando(false);
      });

    return () => abort.abort();
  }, [user?.tenantId, cargandoSesion, reintento]);

  const recargar = useCallback(() => setReintento((n) => n + 1), []);

  if (cargando) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando incumplimientos" />
      </div>
    );
  }

  const total = datos.articulos.length + datos.declaraciones.length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Incumplimientos</h1>
          <p className="text-sm text-slate-500">
            Artículos evaluados como incumplidos y declaraciones vencidas, con la evidencia
            que los respalda.
          </p>
        </div>
        <Button
          variant="secondary"
          size="md"
          onClick={recargar}
          icon={<RefreshCw className="h-4 w-4" aria-hidden />}
        >
          Actualizar
        </Button>
      </div>

      {error && (
        <p role="alert" className="rounded-card border border-semaforo-no-cumple bg-semaforo-no-cumple-bg px-4 py-3 text-sm text-semaforo-no-cumple">
          {error}
        </p>
      )}

      {/* El contador que decide la prioridad del día. Va arriba y aparte porque
          es la pregunta que se hace quien abre esta pantalla. */}
      {datos.articulosSinEvidencia > 0 && (
        <div className="flex items-start gap-3 rounded-card border border-semaforo-parcial bg-semaforo-parcial-bg px-4 py-3">
          <FileWarning className="mt-0.5 h-5 w-5 shrink-0 text-semaforo-parcial" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-slate-800">
              {datos.articulosSinEvidencia}{' '}
              {datos.articulosSinEvidencia === 1
                ? 'incumplimiento sin evidencia'
                : 'incumplimientos sin evidencia'}
            </p>
            <p className="mt-0.5 text-sm text-slate-600">
              Son los que dejan a la empresa sin nada que mostrar ante una fiscalización.
              Van primeros en la lista.
            </p>
          </div>
        </div>
      )}

      {total === 0 && !error && (
        <div className="rounded-card border border-slate-200 bg-white px-4 py-10 text-center">
          <p className="text-sm font-medium text-slate-700">
            No hay incumplimientos registrados.
          </p>
          {/* **No dice "todo en orden".** Que no haya incumplimientos
              *registrados* no significa que no los haya: puede que nadie haya
              evaluado nada todavía, y esa distinción es la que este sistema
              lleva corrigiendo en cada pantalla. */}
          <p className="mt-1 text-sm text-slate-500">
            Ojo: esto cuenta lo evaluado. Un artículo que nadie revisó no aparece acá —
            revisá el avance en la{' '}
            <Link href="/matriz-legal" className="text-brand-600 hover:underline">
              Matriz Legal
            </Link>
            .
          </p>
        </div>
      )}

      {datos.articulos.length > 0 && (
        <section aria-labelledby="articulos-incumplidos" className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <h2 id="articulos-incumplidos" className="text-base font-semibold text-slate-900">
              Artículos incumplidos
              <span className="ml-2 text-sm font-normal text-slate-500">
                {datos.articulos.length}
              </span>
            </h2>
            {datos.articulosTruncados && (
              <p className="text-xs text-slate-500">
                Se muestran los primeros — hay más de los que caben en una consulta.
              </p>
            )}
          </div>

          <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
            <table className="w-full min-w-[820px] text-sm">
              <caption className="sr-only">
                Artículos evaluados como incumplidos, sin evidencia primero
              </caption>
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th scope="col" className="px-4 py-3">Norma</th>
                  <th scope="col" className="px-4 py-3">Artículo</th>
                  <th scope="col" className="px-4 py-3">Planta</th>
                  <th scope="col" className="px-4 py-3">Forma de cumplimiento</th>
                  <th scope="col" className="px-4 py-3">Evidencia</th>
                </tr>
              </thead>
              <tbody>
                {datos.articulos.map((a) => (
                  <tr key={a.articleComplianceId} className="border-b border-slate-100 align-top last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/matriz-legal/${a.normId}`}
                        className="font-medium text-brand-600 hover:underline"
                      >
                        {a.normaNumero}
                      </Link>
                      <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{a.normaTitulo}</p>
                    </td>
                    <td className="px-4 py-3">
                      {/* El atajo que faltaba. Las declaraciones ya enlazaban a
                          su obligación; los artículos dejaban a la persona
                          buscándolos a mano, norma por norma — que es justo lo
                          que esta pantalla existe para evitar.

                          El ancla `#articulo-{id}` importa tanto como el
                          enlace: sin ella, en una norma de 151 artículos la
                          persona aterriza al principio y vuelve a buscar. */}
                      <Link
                        href={`/matriz-legal/${a.normId}#articulo-${a.articuloId}`}
                        className="font-medium text-brand-600 hover:underline"
                      >
                        {a.articuloNumero}
                      </Link>
                      {a.articuloEpigrafe && (
                        <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{a.articuloEpigrafe}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {/* Sin planta = evaluado a nivel de empresa. Se dice, en
                          vez de dejar la celda vacía como si faltara el dato. */}
                      {a.planta ?? <span className="text-slate-400">Toda la empresa</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {a.formaCumplimiento ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      {a.evidenciaUrl ? (
                        <a
                          href={a.evidenciaUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-brand-600 hover:underline"
                        >
                          Ver evidencia
                          <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                        </a>
                      ) : (
                        <span className="inline-flex items-center gap-1 font-medium text-semaforo-parcial">
                          <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                          Sin evidencia
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {datos.declaraciones.length > 0 && (
        <section aria-labelledby="declaraciones-vencidas" className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <h2 id="declaraciones-vencidas" className="text-base font-semibold text-slate-900">
              Declaraciones vencidas
              <span className="ml-2 text-sm font-normal text-slate-500">
                {datos.declaraciones.length}
              </span>
            </h2>
            {datos.declaracionesTruncadas && (
              <p className="text-xs text-slate-500">Se muestran las primeras.</p>
            )}
          </div>

          <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
            <table className="w-full min-w-[720px] text-sm">
              <caption className="sr-only">Declaraciones vencidas, la más antigua primero</caption>
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th scope="col" className="px-4 py-3">Declaración</th>
                  <th scope="col" className="px-4 py-3">Planta</th>
                  <th scope="col" className="px-4 py-3">Atraso</th>
                  <th scope="col" className="px-4 py-3">Estado</th>
                  <th scope="col" className="px-4 py-3">Folio</th>
                </tr>
              </thead>
              <tbody>
                {datos.declaraciones.map((d) => (
                  <tr key={d.obligationId} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link href={`/obligaciones/${d.obligationId}`} className="font-medium text-slate-800 hover:underline">
                        {d.titulo}
                      </Link>
                      <p className="mt-0.5 text-xs text-slate-500">{d.codigo}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {d.planta ?? <span className="text-slate-400">Toda la empresa</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-semibold tabular-nums text-semaforo-no-cumple">
                        {d.diasVencida ?? '—'}
                      </span>
                      <span className="ml-1 text-xs text-slate-500">
                        {d.diasVencida === 1 ? 'día' : 'días'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status="vencida" />
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {d.folio ?? <span className="text-slate-400">Sin folio</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
