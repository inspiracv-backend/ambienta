'use client';

import { useState } from 'react';
import { useNormativaPropia } from '@/lib/usar-normativa-propia';
import { fechaCalendario } from '@/lib/fechas';

/**
 * S-12 — La normativa propia de la empresa (RF-10, RF-11, bloque D).
 *
 * ## Qué resuelve
 *
 * El catálogo normativo es público: 24 normas y 689 artículos compartidos entre
 * todas las empresas, y está bien que lo sea porque la ley es la misma para
 * todos. La consecuencia era que **una empresa no podía registrar su RCA**: su
 * Resolución de Calificación Ambiental es el permiso de *ese* proyecto, y
 * escribirla en el catálogo la habría dejado visible para las demás.
 *
 * ## Lo que esta pantalla NO hace, y lo dice
 *
 * No lee el PDF. RF-11 menciona la extracción asistida como opcional y depende
 * de `ai-service`, que es una carpeta vacía. Acá se registra la norma y sus
 * considerandos se escriben a mano — **cero considerandos no es un error**, es
 * el estado inicial mientras se transcriben.
 */
const FUENTES = [
  { valor: 'RCA', etiqueta: 'RCA — Resolución de Calificación Ambiental' },
  { valor: 'ISO', etiqueta: 'ISO — norma adquirida por la empresa' },
  { valor: 'INTERNAL', etiqueta: 'Interna — procedimiento propio con rango de norma' },
];

export default function NormativaPropiaPage() {
  const { normas, error, guardando, errorAlGuardar, registrar } = useNormativaPropia();
  const [abierto, setAbierto] = useState(false);
  const [fuente, setFuente] = useState('RCA');
  const [titulo, setTitulo] = useState('');
  const [numero, setNumero] = useState('');
  const [organismo, setOrganismo] = useState('');

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const ok = await registrar({
      fuente,
      norm_type: fuente === 'RCA' ? 'resolucion' : 'norma_interna',
      title: titulo.trim(),
      norm_number: numero.trim() || null,
      issuing_body: organismo.trim() || null,
    });
    // Sólo se limpia si se guardó: el número de una RCA cuesta ir a buscarlo.
    if (ok) {
      setTitulo('');
      setNumero('');
      setOrganismo('');
      setAbierto(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Normativa propia</h1>
          <p className="text-sm text-slate-500">
            La RCA de la empresa y sus normas internas. No se comparten con nadie.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setAbierto((v) => !v)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white"
        >
          {abierto ? 'Cancelar' : 'Registrar una norma'}
        </button>
      </header>

      {abierto && (
        <form
          onSubmit={enviar}
          className="flex flex-col gap-3 rounded-card border border-slate-200 bg-white p-5"
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="fuente" className="text-xs font-medium text-slate-600">
              Tipo
            </label>
            <select
              id="fuente"
              value={fuente}
              onChange={(e) => setFuente(e.target.value)}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              {FUENTES.map((f) => (
                <option key={f.valor} value={f.valor}>
                  {f.etiqueta}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="titulo" className="text-xs font-medium text-slate-600">
              Título
            </label>
            <input
              id="titulo"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              required
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <label htmlFor="numero" className="text-xs font-medium text-slate-600">
                Número
              </label>
              <input
                id="numero"
                value={numero}
                onChange={(e) => setNumero(e.target.value)}
                placeholder="RCA-123/2019"
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="organismo" className="text-xs font-medium text-slate-600">
                Organismo que la dictó
              </label>
              <input
                id="organismo"
                value={organismo}
                onChange={(e) => setOrganismo(e.target.value)}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
          </div>

          {errorAlGuardar && (
            <p role="alert" className="text-sm text-semaforo-no-cumple">
              {errorAlGuardar}
            </p>
          )}

          {/* Decirlo acá evita que alguien suba el PDF y espere que el sistema
              lo lea. RF-11 deja esa parte fuera a propósito. */}
          <p className="text-xs text-slate-400">
            Los considerandos se cargan después, uno por uno: el sistema todavía no
            lee el PDF de la resolución.
          </p>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={guardando || !titulo.trim()}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {guardando ? 'Guardando…' : 'Registrar'}
            </button>
          </div>
        </form>
      )}

      {error ? (
        <p role="alert" className="text-sm text-semaforo-no-cumple">
          No se pudo cargar la normativa propia: {error}
        </p>
      ) : normas === null ? (
        <p role="status" className="text-sm text-slate-400">
          Comprobando…
        </p>
      ) : normas.length === 0 ? (
        // «No cargó su RCA» sería una acusación de que falta un permiso;
        // «todavía no se registró ninguna» describe el estado sin afirmarlo.
        <p className="text-sm text-slate-500">
          Todavía no se registró ninguna norma propia.
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-slate-100 rounded-card border border-slate-200 bg-white">
          {normas.map((n) => (
            <li key={n.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 p-4">
              {n.normNumber && (
                <span className="font-medium tabular-nums text-slate-900">
                  {n.normNumber}
                </span>
              )}
              <span className="text-sm text-slate-700">{n.title}</span>
              {n.organismo && <span className="text-xs text-slate-400">{n.organismo}</span>}
              {n.publicadaEl && (
                <span className="text-xs text-slate-400">
                  {fechaCalendario(n.publicadaEl)}
                </span>
              )}
              {/* Cero considerandos **no** es un error: es el estado inicial
                  mientras se transcriben. Se dice, no se esconde. */}
              <span className="ml-auto text-xs tabular-nums text-slate-500">
                {n.articulos === 0
                  ? 'sin considerandos cargados'
                  : `${n.articulos} ${n.articulos === 1 ? 'considerando' : 'considerandos'}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
