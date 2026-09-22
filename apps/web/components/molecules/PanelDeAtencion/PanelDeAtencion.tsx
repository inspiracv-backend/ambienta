'use client';

import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * Un panel que resume **lo que hay que atender**, y que sabe distinguir tres
 * estados que se ven casi iguales.
 *
 * ## Por qué existe como componente y no como un `<ul>` en cada pantalla
 *
 * Porque el error está en el estado vacío, no en la lista. Este proyecto lo
 * cometió cuatro veces —`normSemaforo(0)`, el tablero pintando en rojo las
 * plantas sin evaluar, la cobertura, los reportes— y siempre igual: **dibujar
 * un cero sobre algo que nadie midió**.
 *
 * Los tres estados y por qué no pueden compartir dibujo:
 *
 * | estado | lo que significa | lo que se muestra |
 * |---|---|---|
 * | `undefined` | todavía no volvió la consulta | "Comprobando…" |
 * | error | no se pudo preguntar | el motivo, en tono de alerta |
 * | `[]` | se preguntó y no hay nada | "Nada pendiente", en verde |
 *
 * Los tres se ven como "sin problemas" si se dibujan igual, y sólo uno lo es.
 * En un sistema de cumplimiento el daño es concreto: un panel de vencimientos
 * que dice cero porque la consulta falló hace que nadie renueve nada.
 */
export interface PanelDeAtencionProps {
  titulo: string;
  /** Qué se está mirando, en una frase. Sale bajo el título. */
  explica: string;
  /**
   * Las filas. `null` o `undefined` = **todavía no se sabe**, que no es lo
   * mismo que una lista vacía: la primera es una pregunta sin responder y la
   * segunda es una respuesta.
   *
   * Se aceptan los dos porque son dos vocabularios que se encuentran acá: el
   * store dice `null` —es un dato que puede no haber llegado— y en React una
   * prop ausente es `undefined`. Exigir uno solo obligaría a traducir en cada
   * sitio que lo use, y **una traducción olvidada convierte "no se sabe" en
   * una lista vacía**, que es exactamente el error que este panel evita.
   */
  filas: ReactNode[] | null | undefined;
  /** Por qué no se pudo preguntar, si es que falló. */
  error?: string | null;
  /** Qué decir cuando de verdad no hay nada. */
  vacio: string;
  /** Un dato de contexto para el encabezado, por ejemplo la ventana en días. */
  nota?: string;
}

export function PanelDeAtencion({
  titulo,
  explica,
  filas,
  error,
  vacio,
  nota,
}: PanelDeAtencionProps) {
  const sinResponder = filas === undefined || filas === null;
  const cuantas = filas?.length ?? 0;

  return (
    <section
      className="rounded-card border border-slate-200 bg-white"
      aria-labelledby={`panel-${titulo.replace(/\s+/g, '-').toLowerCase()}`}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <div>
          <h2
            id={`panel-${titulo.replace(/\s+/g, '-').toLowerCase()}`}
            className="text-sm font-semibold text-slate-900"
          >
            {titulo}
          </h2>
          <p className="text-xs text-slate-500">{explica}</p>
        </div>
        {/*
          El contador **no se dibuja mientras no se sabe**. Un "0" al lado del
          título es la afirmación más fuerte de esta pantalla, y afirmarla sobre
          una consulta que no volvió es justo el error que este panel existe
          para no cometer.
        */}
        {!sinResponder && !error && (
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium tabular-nums',
              cuantas > 0
                ? 'bg-semaforo-no-cumple-bg text-semaforo-no-cumple'
                : 'bg-semaforo-cumple-bg text-semaforo-cumple',
            )}
          >
            {cuantas}
          </span>
        )}
        {nota && !sinResponder && !error && (
          <span className="text-xs text-slate-400">{nota}</span>
        )}
      </header>

      <div className="px-4 py-3 text-sm">
        {error ? (
          <p role="alert" className="text-semaforo-no-cumple">
            No se pudo comprobar: {error}
          </p>
        ) : sinResponder ? (
          <p role="status" className="text-slate-400">
            Comprobando…
          </p>
        ) : cuantas === 0 ? (
          <p className="text-semaforo-cumple">{vacio}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-slate-100">
            {filas!.map((fila, i) => (
              <li key={i} className="py-2 first:pt-0 last:pb-0">
                {fila}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
