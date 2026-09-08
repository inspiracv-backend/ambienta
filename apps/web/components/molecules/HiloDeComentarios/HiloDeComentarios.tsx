'use client';

import { useState } from 'react';
import { usarComentarios } from '@/lib/usar-comentarios';
// `fechaDeInstante` y no `fechaCalendario`: `created_at` es una marca de
// tiempo, asi que se convierte a hora local. La otra es para fechas sin hora,
// que pasadas por `new Date` retroceden un dia en todo huso al oeste de
// Greenwich — el defecto que ya aparecio en la pantalla de documentos.
import { fechaDeInstante } from '@/lib/fechas';

interface Props {
  entityType: string;
  entityId: string;
  titulo?: string;
}

/**
 * La conversación sobre un registro (RF-111).
 *
 * ## Por qué existe este componente y no una lista simple
 *
 * Por los estados vacíos, igual que `PanelDeAtencion`. Tres situaciones que se
 * ven casi iguales y sólo una significa «nadie dijo nada»:
 *
 * | estado | significa | muestra |
 * |---|---|---|
 * | `null` | la consulta no volvió | «Comprobando…» |
 * | error | no se pudo preguntar | el motivo, en alerta |
 * | `[]` | se preguntó y no hay nada | el vacío |
 *
 * El cliente dijo que la información se pierde por correo. Un hilo que se ve
 * vacío porque la consulta falló diría justamente lo contrario de lo que este
 * módulo viene a arreglar.
 */
export function HiloDeComentarios({ entityType, entityId, titulo = 'Conversación' }: Props) {
  const { comentarios, error, publicando, publicar, errorAlPublicar } =
    usarComentarios(entityType, entityId);
  const [borrador, setBorrador] = useState('');
  const [respondiendoA, setRespondiendoA] = useState<string | null>(null);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!borrador.trim()) return;
    const ok = await publicar(borrador, { padreId: respondiendoA ?? undefined });
    // **El borrador sólo se limpia si se guardó.** Vaciarlo pase lo que pase
    // es cómo se pierde lo que alguien acaba de escribir cuando el servidor
    // responde mal — el mismo criterio que el registro de actividades del CRM.
    if (ok) {
      setBorrador('');
      setRespondiendoA(null);
    }
  }

  return (
    <div className="rounded-card border border-slate-200 bg-white p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-900">{titulo}</h2>
        {/* El contador no se dibuja mientras no se sabe: un «0» junto al
            título afirma que nadie comentó nunca. */}
        {comentarios !== null && !error && (
          <span className="text-xs tabular-nums text-slate-500">
            {comentarios.length}{' '}
            {comentarios.length === 1 ? 'comentario' : 'comentarios'}
          </span>
        )}
      </div>

      {error ? (
        <p role="alert" className="mt-4 text-sm text-semaforo-no-cumple">
          No se pudo cargar la conversación: {error}
        </p>
      ) : comentarios === null ? (
        <p role="status" className="mt-4 text-sm text-slate-400">
          Comprobando…
        </p>
      ) : comentarios.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">
          Nadie ha comentado sobre este registro todavía.
        </p>
      ) : (
        <ol className="mt-4 flex flex-col gap-4">
          {comentarios.map((c) => (
            <li
              key={c.id}
              className={c.padreId ? 'ml-6 border-l-2 border-slate-100 pl-4' : ''}
            >
              <div className="flex flex-wrap items-baseline gap-x-2 text-xs text-slate-500">
                <span className="font-medium text-slate-900">
                  {c.autor ?? 'Autor desconocido'}
                </span>
                <span>{fechaDeInstante(c.creadoEl)}</span>
                {/* **Editado se muestra.** Un comentario corregido después de
                    que alguien lo respondió cambia lo que quedó escrito, y el
                    hilo se lee como si la respuesta contestara al texto nuevo. */}
                {c.editadoEl && <span className="italic">· editado</span>}
              </div>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{c.cuerpo}</p>
              {!c.padreId && (
                <button
                  type="button"
                  onClick={() => setRespondiendoA(c.id)}
                  className="mt-1 text-xs text-brand-600 hover:underline"
                >
                  Responder
                </button>
              )}
            </li>
          ))}
        </ol>
      )}

      <form onSubmit={enviar} className="mt-5 flex flex-col gap-2">
        {respondiendoA && (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>Respondiendo a un comentario del hilo</span>
            <button
              type="button"
              onClick={() => setRespondiendoA(null)}
              className="text-brand-600 hover:underline"
            >
              Cancelar
            </button>
          </div>
        )}
        <label htmlFor="comentario-nuevo" className="sr-only">
          Escribir un comentario
        </label>
        <textarea
          id="comentario-nuevo"
          value={borrador}
          onChange={(e) => setBorrador(e.target.value)}
          rows={3}
          placeholder="Dejar constancia de algo sobre este registro…"
          className="w-full rounded-lg border border-slate-200 p-3 text-sm"
        />
        {errorAlPublicar && (
          <p role="alert" className="text-sm text-semaforo-no-cumple">
            {errorAlPublicar}
          </p>
        )}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={publicando || !borrador.trim()}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {publicando ? 'Publicando…' : 'Comentar'}
          </button>
        </div>
      </form>
    </div>
  );
}
