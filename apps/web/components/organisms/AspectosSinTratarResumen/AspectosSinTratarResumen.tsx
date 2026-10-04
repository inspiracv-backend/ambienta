'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Leaf } from 'lucide-react';
import { ApiError, api, mensajeDeError } from '@/lib/api-client';

type Estado =
  | { tipo: 'cargando' }
  | { tipo: 'listo'; cantidad: number }
  | { tipo: 'sin_permiso' }
  | { tipo: 'error'; mensaje: string };

/**
 * Cuántos aspectos significativos no tienen riesgo u oportunidad asociado (ISO
 * 14001 §6.1.4), en el tablero. Es el hallazgo más común de una auditoría de
 * 14001 y hasta el 21-sep solo se veía entrando a la pantalla de aspectos.
 *
 * Sale de la misma vista que el panel "Significativos sin tratar" de esa
 * pantalla (`/iso14001/aspects/significant-untreated`), así que los dos dicen
 * el mismo número.
 *
 * Tres estados distintos, y ninguno se disfraza de otro:
 *
 * - **Sin permiso (403)**: no se muestra. No es un módulo de esa persona.
 * - **Error**: lo dice. Un `0` ahí sería la afirmación más tranquilizadora de
 *   la pantalla, y falsa.
 * - **Cero**: se muestra, en verde. Es un dato.
 */
export function AspectosSinTratarResumen({ tenantId }: { tenantId: string }) {
  const [estado, setEstado] = useState<Estado>({ tipo: 'cargando' });

  useEffect(() => {
    let cancelado = false;
    setEstado({ tipo: 'cargando' });
    api
      .get<unknown[]>('/iso14001/aspects/significant-untreated', { tenantId })
      .then((filas) => {
        if (!cancelado) setEstado({ tipo: 'listo', cantidad: filas.length });
      })
      .catch((e: unknown) => {
        if (cancelado) return;
        if (e instanceof ApiError && e.status === 403) setEstado({ tipo: 'sin_permiso' });
        else setEstado({ tipo: 'error', mensaje: mensajeDeError(e) });
      });
    return () => {
      cancelado = true;
    };
  }, [tenantId]);

  if (estado.tipo === 'sin_permiso' || estado.tipo === 'cargando') return null;

  if (estado.tipo === 'error') {
    return (
      <p role="alert" className="rounded-card bg-semaforo-no-cumple-bg px-4 py-3 text-sm text-semaforo-no-cumple">
        No se pudo consultar los aspectos significativos sin tratar: {estado.mensaje}
      </p>
    );
  }

  const hayPendientes = estado.cantidad > 0;
  return (
    <Link
      href="/aspectos-ambientales"
      className="flex items-center justify-between gap-4 rounded-card border border-slate-200 bg-white p-5 hover:border-slate-300"
    >
      <span className="flex items-center gap-3">
        <Leaf
          className={hayPendientes ? 'h-5 w-5 text-semaforo-parcial' : 'h-5 w-5 text-semaforo-cumple'}
          aria-hidden
        />
        <span>
          <span className="block text-sm font-medium text-slate-900">
            Aspectos significativos sin tratar
          </span>
          <span className="block text-xs text-slate-500">
            {hayPendientes
              ? 'Sin riesgo ni oportunidad asociados (ISO 14001 §6.1.4)'
              : 'Todos los aspectos significativos tienen tratamiento'}
          </span>
        </span>
      </span>
      <span
        className={
          hayPendientes
            ? 'text-2xl font-semibold tabular-nums text-semaforo-parcial'
            : 'text-2xl font-semibold tabular-nums text-semaforo-cumple'
        }
      >
        {estado.cantidad}
      </span>
    </Link>
  );
}
