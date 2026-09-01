'use client';

import { useId, useState } from 'react';
import { AlertTriangle, GripVertical, Trophy, XCircle } from 'lucide-react';
import { Button, Textarea } from '@/components/atoms';
import {
  formatearFecha,
  formatearMonto,
  necesitaMotivo,
  resumenDeColumna,
  type EtapaCrm,
  type TratoCrm,
} from '@/lib/crm';
import type { PipelineKanbanProps } from './PipelineKanban.types';

/**
 * El kanban del pipeline comercial (#81).
 *
 * ## Se arrastra, y además se puede mover sin arrastrar
 *
 * El tablero usa la API de arrastre nativa del navegador, sin librería. Eso
 * trae una limitación que **no es un detalle de accesibilidad opcional**:
 * `dragstart` no existe en pantallas táctiles ni con teclado. Ambienta es una
 * PWA, y quien la usa en un tablet dentro de una planta no puede arrastrar
 * nada.
 *
 * Por eso cada tarjeta tiene también un selector "Mover a", que es un
 * `<select>` de verdad: funciona con dedo, con teclado y con lector de
 * pantalla. El arrastre es el atajo para quien tiene mouse, no el único
 * camino. Poner solo el arrastre habría dejado el módulo inutilizable en
 * teléfono sin que nada lo dijera.
 *
 * ## Los números salen del servidor
 *
 * La cabecera muestra `totalTratos` y los montos tal como vienen: las columnas
 * llegan cortadas en el tope, así que contar las tarjetas visibles daría un
 * número menor que el real. Y los montos van **por moneda**, porque sumar CLP
 * con USD da una cifra que no es plata de ninguna clase.
 */
export function PipelineKanban({ pipeline, onMover, onAbrirTrato }: PipelineKanbanProps) {
  const [arrastrando, setArrastrando] = useState<TratoCrm | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);
  const [pidiendoMotivo, setPidiendoMotivo] = useState<{
    trato: TratoCrm;
    destino: EtapaCrm;
  } | null>(null);
  const [motivo, setMotivo] = useState('');
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const etapas = pipeline.columnas.map((c) => c.etapa);

  async function ejecutar(trato: TratoCrm, destino: EtapaCrm, razon?: string) {
    setOcupado(true);
    const r = await onMover(trato, destino, razon);
    setOcupado(false);
    if (!r.ok) {
      setAviso({ tipo: 'error', texto: r.error ?? 'No se pudo mover la oportunidad.' });
      return;
    }
    // Se anuncia lo que pasó **además** de cambiar de columna. Sin esto,
    // arrastrar a "Perdido" cierra el trato en silencio.
    setAviso({
      tipo: 'ok',
      texto:
        r.efectos.length > 0
          ? `${trato.titulo} → ${destino.nombre}. ${r.efectos.join('. ')}.`
          : `${trato.titulo} pasó a ${destino.nombre}.`,
    });
  }

  function intentarMover(trato: TratoCrm, destino: EtapaCrm) {
    if (trato.etapaId === destino.id) return;
    if (necesitaMotivo(destino)) {
      // Se pregunta antes de mandar: quien mueve un trato a "Perdido" espera
      // que le pidan la razón, no que el servidor le rechace el movimiento.
      setMotivo('');
      setPidiendoMotivo({ trato, destino });
      return;
    }
    void ejecutar(trato, destino);
  }

  return (
    <div className="flex flex-col gap-3">
      {pipeline.truncado && (
        <p className="flex items-start gap-2 rounded-card border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Alguna columna tiene más oportunidades de las que caben en el tablero. Los
            totales de la cabecera sí las cuentan todas.
          </span>
        </p>
      )}

      {/*
        El contenedor va **siempre montado** aunque esté vacío, y el mensaje
        vive adentro. Dos razones, y las dos importan:

        - Un `aria-live` que aparece junto con su contenido no se anuncia en
          varios lectores de pantalla: la región tiene que existir antes de que
          el texto cambie.
        - Es un solo elemento y no dos. La versión anterior tenía una copia
          `sr-only` y otra visible, así que el mismo mensaje estaba dos veces en
          el DOM — un lector de pantalla podía leerlo repetido.
      */}
      <div aria-live="polite">
        {aviso && (
          <p
            className={
              aviso.tipo === 'ok'
                ? 'rounded-card border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800'
                : 'rounded-card border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800'
            }
          >
            {aviso.texto}
          </p>
        )}
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2">
        {pipeline.columnas.map((col) => {
          const esDestinoActivo = sobre === col.etapa.id && arrastrando !== null;
          return (
            <section
              key={col.etapa.id}
              aria-label={`${col.etapa.nombre}, ${col.totalTratos} oportunidades`}
              onDragOver={(e) => {
                if (!arrastrando) return;
                e.preventDefault();
                setSobre(col.etapa.id);
              }}
              onDragLeave={() => setSobre((s) => (s === col.etapa.id ? null : s))}
              onDrop={(e) => {
                e.preventDefault();
                setSobre(null);
                const t = arrastrando;
                setArrastrando(null);
                if (t) intentarMover(t, col.etapa);
              }}
              className={[
                'flex w-72 shrink-0 flex-col gap-2 rounded-card border p-3 transition-colors',
                esDestinoActivo
                  ? 'border-brand-400 bg-brand-50'
                  : 'border-slate-200 bg-slate-50',
              ].join(' ')}
            >
              <header className="px-1">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {col.etapa.tipo === 'won' && (
                      <Trophy className="h-3.5 w-3.5 text-emerald-600" aria-hidden />
                    )}
                    {col.etapa.tipo === 'lost' && (
                      <XCircle className="h-3.5 w-3.5 text-red-500" aria-hidden />
                    )}
                    {col.etapa.nombre}
                  </h3>
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                    {col.totalTratos}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{resumenDeColumna(col)}</p>
              </header>

              <div className="flex flex-col gap-2">
                {col.tratos.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-slate-200 p-3 text-center text-xs text-slate-400">
                    {col.totalTratos === 0 ? 'Sin oportunidades' : 'Nada que mostrar'}
                  </p>
                ) : (
                  col.tratos.map((trato) => (
                    <TarjetaDeTrato
                      key={trato.id}
                      trato={trato}
                      etapas={etapas}
                      deshabilitado={ocupado}
                      onArrastrar={setArrastrando}
                      onSoltar={() => {
                        setArrastrando(null);
                        setSobre(null);
                      }}
                      onMoverA={(destino) => intentarMover(trato, destino)}
                      onAbrir={onAbrirTrato ? () => onAbrirTrato(trato) : undefined}
                    />
                  ))
                )}
                {col.totalTratos > col.tratos.length && (
                  <p className="px-1 text-xs text-slate-400">
                    y {col.totalTratos - col.tratos.length} más que no caben acá
                  </p>
                )}
              </div>
            </section>
          );
        })}
      </div>

      {pidiendoMotivo && (
        <MotivoDeLaPerdida
          titulo={pidiendoMotivo.trato.titulo}
          etapa={pidiendoMotivo.destino.nombre}
          motivo={motivo}
          onMotivo={setMotivo}
          ocupado={ocupado}
          onCancelar={() => setPidiendoMotivo(null)}
          onConfirmar={() => {
            const { trato, destino } = pidiendoMotivo;
            setPidiendoMotivo(null);
            void ejecutar(trato, destino, motivo);
          }}
        />
      )}
    </div>
  );
}

function TarjetaDeTrato({
  trato,
  etapas,
  deshabilitado,
  onArrastrar,
  onSoltar,
  onMoverA,
  onAbrir,
}: {
  trato: TratoCrm;
  etapas: EtapaCrm[];
  deshabilitado: boolean;
  onArrastrar: (t: TratoCrm) => void;
  onSoltar: () => void;
  onMoverA: (destino: EtapaCrm) => void;
  onAbrir?: () => void;
}) {
  const idSelect = useId();
  return (
    <article
      draggable={!deshabilitado}
      onDragStart={() => onArrastrar(trato)}
      onDragEnd={onSoltar}
      className="rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm"
    >
      <div className="flex items-start gap-1.5">
        <GripVertical
          className="mt-0.5 h-4 w-4 shrink-0 cursor-grab text-slate-300"
          aria-hidden
        />
        <div className="min-w-0 flex-1">
          {onAbrir ? (
            <button
              type="button"
              onClick={onAbrir}
              className="text-left font-medium text-slate-800 hover:text-brand-700 hover:underline"
            >
              {trato.titulo}
            </button>
          ) : (
            <p className="font-medium text-slate-800">{trato.titulo}</p>
          )}
          <p className="mt-0.5 text-xs text-slate-500">
            {trato.monto === null ? (
              // "Sin valorar" y no "$ 0": un trato al que nadie le puso cifra
              // no es un trato que no vale nada.
              <span className="italic text-slate-400">Sin valorar</span>
            ) : (
              formatearMonto(trato.monto, trato.moneda)
            )}
            {' · '}
            {formatearFecha(trato.cierreEstimado)}
          </p>
          {trato.motivoPerdida && (
            <p className="mt-1 rounded bg-red-50 px-1.5 py-0.5 text-xs text-red-700">
              {trato.motivoPerdida}
            </p>
          )}
        </div>
      </div>

      {/*
        El camino sin arrastre. No es un extra: `dragstart` no existe en táctil
        ni con teclado, así que sin esto el tablero no se puede usar en un
        teléfono ni sin mouse.
      */}
      <label htmlFor={idSelect} className="sr-only">
        Mover {trato.titulo} a otra etapa
      </label>
      <select
        id={idSelect}
        value=""
        disabled={deshabilitado}
        onChange={(e) => {
          const destino = etapas.find((x) => x.id === e.target.value);
          if (destino) onMoverA(destino);
          e.target.value = '';
        }}
        className="mt-2 w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 disabled:opacity-50"
      >
        <option value="">Mover a…</option>
        {etapas
          .filter((x) => x.id !== trato.etapaId)
          .map((x) => (
            <option key={x.id} value={x.id}>
              {x.nombre}
            </option>
          ))}
      </select>
    </article>
  );
}

/**
 * Perder exige decir por qué.
 *
 * Se pide acá y no se deja al 422 del servidor porque el movimiento ya ocurrió
 * en la cabeza de quien arrastró: pedirle la razón es continuar la acción, y
 * rechazársela es interrumpirla.
 */
function MotivoDeLaPerdida({
  titulo,
  etapa,
  motivo,
  onMotivo,
  ocupado,
  onCancelar,
  onConfirmar,
}: {
  titulo: string;
  etapa: string;
  motivo: string;
  onMotivo: (v: string) => void;
  ocupado: boolean;
  onCancelar: () => void;
  onConfirmar: () => void;
}) {
  const vacio = motivo.trim().length === 0;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="motivo-titulo"
        className="w-full max-w-md rounded-card bg-white p-5 shadow-lg"
      >
        <h2 id="motivo-titulo" className="text-base font-semibold text-slate-900">
          ¿Por qué se perdió?
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          <span className="font-medium">{titulo}</span> pasa a {etapa}. Aprender por qué
          se pierde es la razón de tener un pipeline, así que el motivo es obligatorio.
        </p>
        <Textarea
          value={motivo}
          onChange={(e) => onMotivo(e.target.value)}
          rows={3}
          placeholder="El cliente eligió a la competencia por precio"
          className="mt-3"
          aria-label="Motivo de la pérdida"
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancelar} disabled={ocupado}>
            Cancelar
          </Button>
          <Button variant="danger" onClick={onConfirmar} disabled={vacio} isLoading={ocupado}>
            Marcar como perdido
          </Button>
        </div>
      </div>
    </div>
  );
}
