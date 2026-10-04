'use client';

import { useCallback, useEffect, useId, useState } from 'react';
import Link from 'next/link';
import { Plus } from 'lucide-react';
import { Button, Textarea } from '@/components/atoms';
import { mensajeDeError } from '@/lib/api-client';
import { fechaDeInstante } from '@/lib/fechas';
import {
  ESTADO_AUDITORIA_LABEL,
  RESULTADO_LABEL,
  TIPO_AUDITORIA_LABEL,
  TRANSICIONES,
  agregarPregunta,
  avanzarAuditoria,
  cargarChecklist,
  cargarCobertura,
  checklistAbierto,
  leerAuditoria,
  quitarPregunta,
  responderPregunta,
  type Auditoria,
  type Cobertura,
  type EstadoAuditoria,
  type Pregunta,
  type ResultadoPregunta,
  type TipoAuditoria,
} from '@/lib/ciclo-de-auditoria';

export interface CicloDeAuditoriaPanelProps {
  auditId: string;
  tenantId: string;
  /** Procesos de la empresa (`/processes/`), para decir qué proceso revisa cada pregunta. */
  procesos: { id: string; nombre: string }[];
  /** Con el estado que la API confirmó, para que la lista lo refleje. */
  onEstadoCambiado?: (estado: EstadoAuditoria) => void;
}

/** Estas dos piden confirmación: no tienen vuelta atrás. */
const IRREVERSIBLES: EstadoAuditoria[] = ['closed', 'cancelled'];

const RESULTADOS = Object.keys(RESULTADO_LABEL) as ResultadoPregunta[];

/**
 * Ejecutar una auditoría (RF-92, RF-93): su estado, el checklist y cuánto cubre.
 *
 * Lo que decide qué se puede hacer es **lo que responde la API**, no lo que se
 * escribió en pantalla: los botones salen de las transiciones del estado real,
 * y al cerrar o cancelar el checklist queda de solo lectura porque la API lo
 * rechaza con 409.
 */
export function CicloDeAuditoriaPanel({ auditId, tenantId, procesos, onEstadoCambiado }: CicloDeAuditoriaPanelProps) {
  const formId = useId();
  const [auditoria, setAuditoria] = useState<Auditoria | null>(null);
  const [preguntas, setPreguntas] = useState<Pregunta[] | null>(null);
  const [cobertura, setCobertura] = useState<Cobertura | null>(null);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  /** La pregunta que se esta guardando: sus controles se apagan mientras viaja. */
  const [guardandoId, setGuardandoId] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState<EstadoAuditoria | null>(null);
  const [nueva, setNueva] = useState('');
  const [procesoNueva, setProcesoNueva] = useState('');
  const [borradores, setBorradores] = useState<Record<string, { resultado: ResultadoPregunta; notas: string }>>({});

  const recargarCobertura = useCallback(() => {
    cargarCobertura(tenantId, auditId)
      .then(setCobertura)
      // La cobertura informa, no bloquea: sin ella se sigue trabajando.
      .catch(() => setCobertura(null));
  }, [tenantId, auditId]);

  useEffect(() => {
    let vigente = true;
    Promise.all([leerAuditoria(tenantId, auditId), cargarChecklist(tenantId, auditId)])
      .then(([a, p]) => {
        if (!vigente) return;
        setAuditoria(a);
        setPreguntas(p);
        setErrorDeCarga(null);
      })
      .catch((e) => {
        if (vigente) setErrorDeCarga(mensajeDeError(e));
      });
    recargarCobertura();
    return () => {
      vigente = false;
    };
  }, [tenantId, auditId, recargarCobertura]);

  if (errorDeCarga) {
    return (
      <section className="rounded-card border border-slate-200 bg-white p-6">
        <p role="alert" className="text-sm text-semaforo-no-cumple">
          No se pudo cargar la auditoría: {errorDeCarga}
        </p>
      </section>
    );
  }
  if (!auditoria || !preguntas) {
    return (
      <section className="rounded-card border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-500">Cargando la auditoría…</p>
      </section>
    );
  }

  const abierto = checklistAbierto(auditoria.estado);
  const sinResponder = preguntas.filter((p) => p.resultado === 'pending').length;
  const nombreProceso = (id: string | null) => procesos.find((p) => p.id === id)?.nombre ?? null;

  async function avanzar(estado: EstadoAuditoria) {
    if (IRREVERSIBLES.includes(estado) && confirmando !== estado) {
      setConfirmando(estado);
      return;
    }
    setConfirmando(null);
    setOcupado(true);
    setError(null);
    try {
      const a = await avanzarAuditoria(tenantId, auditId, estado);
      setAuditoria(a);
      onEstadoCambiado?.(a.estado);
    } catch (e) {
      setError(`No cambió el estado: ${mensajeDeError(e)}`);
    } finally {
      setOcupado(false);
    }
  }

  async function agregar() {
    if (!nueva.trim()) return;
    setOcupado(true);
    setError(null);
    try {
      const p = await agregarPregunta(tenantId, auditId, nueva, procesoNueva || null);
      setPreguntas((prev) => [...(prev ?? []), p].sort((a, b) => a.secuencia - b.secuencia));
      setNueva('');
      recargarCobertura();
    } catch (e) {
      setError(`No se agregó la pregunta: ${mensajeDeError(e)}`);
    } finally {
      setOcupado(false);
    }
  }

  async function guardar(p: Pregunta) {
    const enviado = borradores[p.id];
    if (!enviado) return;
    setOcupado(true);
    setGuardandoId(p.id);
    setError(null);
    try {
      const actualizada = await responderPregunta(tenantId, auditId, p.id, enviado.resultado, enviado.notas);
      setPreguntas((prev) => (prev ?? []).map((x) => (x.id === p.id ? actualizada : x)));
      // **Solo se descarta lo que se mando.** Si entre el envio y la respuesta
      // se siguio escribiendo, borrar el borrador entero se comia esas letras
      // sin decir nada. Los controles ademas quedan apagados mientras viaja.
      setBorradores((prev) => {
        const actual = prev[p.id];
        if (!actual || actual.resultado !== enviado.resultado || actual.notas !== enviado.notas) return prev;
        const { [p.id]: _guardado, ...resto } = prev;
        return resto;
      });
    } catch (e) {
      setError(`No se guardó la respuesta a la pregunta ${p.secuencia}: ${mensajeDeError(e)}`);
    } finally {
      setOcupado(false);
      setGuardandoId(null);
    }
  }

  async function quitar(p: Pregunta) {
    setOcupado(true);
    setError(null);
    try {
      await quitarPregunta(tenantId, auditId, p.id);
      setPreguntas((prev) => (prev ?? []).filter((x) => x.id !== p.id));
      recargarCobertura();
    } catch (e) {
      setError(`No se quitó la pregunta ${p.secuencia}: ${mensajeDeError(e)}`);
    } finally {
      setOcupado(false);
    }
  }

  const tipo = TIPO_AUDITORIA_LABEL[auditoria.tipo as TipoAuditoria] ?? auditoria.tipo;

  return (
    <section aria-labelledby={`${formId}-titulo`} className="flex flex-col gap-4 rounded-card border border-slate-200 bg-white p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id={`${formId}-titulo`} className="text-sm font-semibold text-slate-700">
            Ejecución de la auditoría
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            <span className="font-medium text-slate-900">{ESTADO_AUDITORIA_LABEL[auditoria.estado] ?? auditoria.estado}</span>
            {' · '}
            {tipo}
            {auditoria.inicioReal && ` · iniciada el ${fechaDeInstante(auditoria.inicioReal)}`}
            {auditoria.finReal && ` · cerrada el ${fechaDeInstante(auditoria.finReal)}`}
          </p>
          {auditoria.alcance && <p className="mt-1 max-w-prose text-sm text-slate-500">Alcance: {auditoria.alcance}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {(TRANSICIONES[auditoria.estado] ?? []).map((t) => (
            <Button
              key={t.a}
              size="sm"
              variant={t.a === 'cancelled' ? 'ghost' : 'primary'}
              // **Se apagan mientras se confirma.** Con el boton vivo, el segundo
              // clic de un doble clic cumplia `confirmando === estado` y cerraba
              // la auditoria sin que nadie leyera el aviso: la confirmacion no
              // protegia de lo unico de lo que tenia que proteger.
              disabled={ocupado || confirmando !== null}
              onClick={() => void avanzar(t.a)}
            >
              {t.accion}
            </Button>
          ))}
        </div>
      </header>

      {confirmando && (
        <div role="alertdialog" aria-labelledby={`${formId}-confirmar`} className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p id={`${formId}-confirmar`}>
            {confirmando === 'closed' ? '¿Cerrar la auditoría?' : '¿Cancelar la auditoría?'} El checklist quedará de solo
            lectura y no se puede deshacer.
            {confirmando === 'closed' && sinResponder > 0 &&
              ` Quedan ${sinResponder} ${sinResponder === 1 ? 'pregunta' : 'preguntas'} sin responder.`}
          </p>
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="danger" disabled={ocupado} onClick={() => void avanzar(confirmando)}>
              Confirmar
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setConfirmando(null)}>
              Volver
            </Button>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm text-semaforo-no-cumple">
          {error}
        </p>
      )}

      <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-slate-100 pt-4">
        <h3 className="text-sm font-semibold text-slate-700">
          Checklist <span className="font-normal text-slate-500">({preguntas.length} {preguntas.length === 1 ? 'pregunta' : 'preguntas'}, {sinResponder} sin responder)</span>
        </h3>
        {cobertura && (
          <p className="text-xs text-slate-500">
            {cobertura.porcentaje === null
              ? 'Cobertura: no hay artículos evaluados que cubrir.'
              : `Cobertura: ${cobertura.cubiertos} de ${cobertura.aplicables} artículos aplicables (${Math.round(cobertura.porcentaje)} %).`}
            {cobertura.preguntasSinArticulo > 0 && ` ${cobertura.preguntasSinArticulo} de proceso, sin artículo.`}
          </p>
        )}
      </div>

      {preguntas.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          Sin preguntas todavía.{abierto ? ' Agrega la primera abajo.' : ''}
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {preguntas.map((p) => {
            const b = borradores[p.id] ?? { resultado: p.resultado, notas: p.notas };
            const cambiada = !!borradores[p.id];
            const proceso = nombreProceso(p.procesoId);
            return (
              <li key={p.id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-sm text-slate-800">
                    <span className="mr-1 font-medium text-slate-500">{p.secuencia}.</span>
                    {p.pregunta}
                  </p>
                  {proceso && <span className="text-xs text-slate-500">Proceso: {proceso}</span>}
                </div>

                {abierto ? (
                  <div className="mt-2 grid gap-2 sm:grid-cols-[12rem_1fr_auto]">
                    <select
                      aria-label={`Resultado de la pregunta ${p.secuencia}`}
                      className="h-9 rounded-lg border border-slate-300 px-2 text-sm disabled:bg-slate-100"
                      disabled={guardandoId === p.id}
                      value={b.resultado}
                      onChange={(e) =>
                        setBorradores((prev) => ({ ...prev, [p.id]: { ...b, resultado: e.target.value as ResultadoPregunta } }))
                      }
                    >
                      {RESULTADOS.map((r) => (
                        <option key={r} value={r}>
                          {RESULTADO_LABEL[r]}
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label={`Evidencia de la pregunta ${p.secuencia}`}
                      placeholder="Evidencia revisada"
                      disabled={guardandoId === p.id}
                      className="h-9 rounded-lg border border-slate-300 px-2 text-sm disabled:bg-slate-100"
                      value={b.notas}
                      onChange={(e) => setBorradores((prev) => ({ ...prev, [p.id]: { ...b, notas: e.target.value } }))}
                    />
                    <div className="flex gap-2">
                      <Button size="sm" disabled={!cambiada || ocupado} onClick={() => void guardar(p)}>
                        Guardar
                      </Button>
                      <Button size="sm" variant="ghost" disabled={ocupado} onClick={() => void quitar(p)}>
                        Quitar
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-600">
                    <span className="font-medium">{RESULTADO_LABEL[p.resultado] ?? p.resultado}</span>
                    {p.notas && ` · ${p.notas}`}
                  </p>
                )}

                {p.resultado === 'nonconform' && !cambiada && (
                  <Link
                    href={`/no-conformidades/nueva?auditId=${auditId}&auditItemId=${p.id}${auditoria.plantaId ? `&plantId=${auditoria.plantaId}` : ''}`}
                    className="mt-2 inline-block text-sm text-brand-600 hover:underline"
                  >
                    Registrar el hallazgo de esta pregunta
                  </Link>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {abierto && (
        <div className="flex flex-col gap-2 border-t border-slate-100 pt-4">
          <label htmlFor={`${formId}-nueva`} className="text-sm font-medium text-slate-700">
            Nueva pregunta
          </label>
          <Textarea id={`${formId}-nueva`} rows={2} value={nueva} onChange={(e) => setNueva(e.target.value)} />
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Proceso de la nueva pregunta"
              className="h-9 rounded-lg border border-slate-300 px-2 text-sm"
              value={procesoNueva}
              onChange={(e) => setProcesoNueva(e.target.value)}
            >
              <option value="">Sin proceso (requisito general)</option>
              {procesos.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              disabled={!nueva.trim() || ocupado}
              icon={<Plus className="h-4 w-4" aria-hidden />}
              onClick={() => void agregar()}
            >
              Agregar pregunta
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
