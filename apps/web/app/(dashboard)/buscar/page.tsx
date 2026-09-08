'use client';

import { useState } from 'react';
import { Search } from 'lucide-react';
import { usarBusqueda } from '@/lib/usar-busqueda';

/**
 * S-40 — El buscador transversal (RF-114, #76).
 *
 * ## Qué resuelve
 *
 * Los otros tres cambios de la épica repartieron la información: el documento
 * cuelga de la obligación, la conversación vive en el registro, la historia se
 * reúne por entidad. Todo eso se encuentra **si ya sabés a qué ficha entrar**.
 *
 * La pregunta de un fiscalizador no tiene esa forma: dice «muéstreme lo de los
 * residuos peligrosos», y eso está repartido entre una norma, tres
 * obligaciones, un procedimiento y el comentario donde alguien explicó por qué
 * se declaró tarde.
 *
 * ## Los cuatro estados
 *
 * | estado | significa |
 * |---|---|
 * | `null` | todavía no se buscó — **no** «no hay nada» |
 * | error | no se pudo buscar |
 * | `[]` | se buscó y no hay coincidencias |
 * | cortado | hay más de lo que se muestra |
 */
const ETIQUETA: Record<string, string> = {
  document: 'Documentos',
  obligation: 'Obligaciones',
  legal_norm: 'Normas',
  nonconformity: 'Hallazgos',
  audit: 'Auditorías',
  environmental_aspect: 'Aspectos ambientales',
  risk_opportunity: 'Riesgos y oportunidades',
  regulated_equipment: 'Equipos regulados',
  process: 'Procesos',
  comment: 'Comentarios',
};

export default function BuscarPage() {
  const { grupos, error, buscando, advertencias, buscar } = usarBusqueda();
  const [texto, setTexto] = useState('');

  const total = grupos?.reduce((n, g) => n + g.coincidencias.length, 0) ?? 0;

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold text-slate-900">Buscar</h1>
        <p className="text-sm text-slate-500">
          Documentos, comentarios y registros de toda la empresa.
        </p>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void buscar(texto.trim());
        }}
        className="flex gap-2"
        role="search"
      >
        <label htmlFor="q" className="sr-only">
          Qué buscar
        </label>
        <input
          id="q"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Una norma, un folio, una palabra de un comentario…"
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={buscando || texto.trim().length < 2}
          className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          <Search className="h-4 w-4" aria-hidden />
          {buscando ? 'Buscando…' : 'Buscar'}
        </button>
      </form>

      {error && (
        <p role="alert" className="text-sm text-semaforo-no-cumple">
          No se pudo buscar: {error}
        </p>
      )}

      {/* `null` es «todavía no se buscó». Decir «sin coincidencias» acá sería
          una afirmación sobre una pregunta que nadie hizo. */}
      {grupos === null && !error && (
        <p className="text-sm text-slate-400">
          Escribí al menos dos caracteres y presioná Buscar.
        </p>
      )}

      {grupos !== null && total === 0 && !error && (
        <p className="text-sm text-slate-500">
          Sin coincidencias. Probá con menos palabras o con un código.
        </p>
      )}

      {(grupos ?? []).map((g) => (
        <section key={g.tipo} className="rounded-card border border-slate-200 bg-white p-5">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-900">
              {ETIQUETA[g.tipo] ?? g.tipo}
            </h2>
            <span className="text-xs tabular-nums text-slate-500">
              {g.coincidencias.length}
            </span>
          </div>

          <ul className="mt-3 flex flex-col divide-y divide-slate-100">
            {g.coincidencias.map((c) => (
              <li key={`${c.tipo}-${c.id}`} className="flex flex-wrap items-baseline gap-x-3 py-2 first:pt-0 last:pb-0">
                {c.codigo && (
                  <span className="font-medium tabular-nums text-slate-900">{c.codigo}</span>
                )}
                <span className="text-sm text-slate-700">{c.titulo}</span>
              </li>
            ))}
          </ul>

          {g.hayMas && (
            <p className="mt-2 text-xs text-slate-400">
              {/* Un grupo cortado en silencio hace que alguien deje de buscar. */}
              Hay más coincidencias de este tipo; acotá la búsqueda para verlas.
            </p>
          )}
        </section>
      ))}

      {grupos !== null && advertencias.length > 0 && (
        <div className="text-xs text-slate-400">
          {/* **No se busca dentro de los archivos.** Sin decirlo, quien busque
              una frase que está en el PDF de un procedimiento concluiría que
              ese procedimiento no la menciona. */}
          {advertencias.map((a) => (
            <p key={a}>{a}</p>
          ))}
        </div>
      )}
    </div>
  );
}
