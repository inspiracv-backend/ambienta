'use client';

import { useEffect, useId, useState } from 'react';
import {
  METODOLOGIAS_ANALISIS_CAUSA,
  SALIDAS_REGLAMENTARIAS,
  puedeCerrarse,
  salidasComprometidas,
  salidasPendientes,
  type EtapaAccionCorrectiva,
  type EtapaAnalisisCausa,
  type EtapaCorreccion,
  type EtapaSeguimiento,
  type SalidaTratamiento,
  type TipoSalida,
} from '@ambienta/shared';
import { Button } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useAudits } from '@/lib/audits-store';

const INPUT = 'h-11 w-full rounded-lg border border-slate-300 px-3 text-sm';
const AREA = 'w-full rounded-lg border border-slate-300 p-3 text-sm';

/** Las cuatro preguntas de §10.2.1, con la redaccion literal del cliente. */
const PREGUNTAS_SEGUIMIENTO: { campo: keyof EtapaSeguimiento; label: string; clausula?: string }[] =
  [
    { campo: 'causaSeRepitio', label: '¿La causa se ha vuelto a repetir durante el periodo de seguimiento?' },
    { campo: 'cumplioProposito', label: '¿La acción correctiva cumplió su propósito?', clausula: '§10.2.1 d' },
    { campo: 'requiereActualizarRiesgos', label: '¿Se requiere actualizar los riesgos y oportunidades?', clausula: '§10.2.1 e' },
    { campo: 'requiereActualizarFoda', label: '¿Se requiere actualizar la matriz FODA?' },
    { campo: 'requiereCambiosSGC', label: '¿Se requiere hacer cambios al sistema de gestión de calidad?', clausula: '§10.2.1 f' },
  ];

/** Convierte el tri-estado a los valores del desplegable del cliente. */
function aSelect(v: boolean | null | undefined): string {
  if (v === true) return 'SI';
  if (v === false) return 'NO';
  return '';
}
function deSelect(v: string): boolean | null {
  if (v === 'SI') return true;
  if (v === 'NO') return false;
  return null;
}

interface Props {
  ncId: string;
  responsableOptions: { id: string; nombre: string }[];
  /** Riesgo y oportunidad no recorren corrección ni análisis de causa. */
  flujoCorto?: boolean;
  /**
   * Informa hacia arriba el resultado de la verificación de eficacia.
   *
   * El cierre NO vive en este panel: vive en el bloque de Cierre con firma, que
   * es el que registra en el audit log. Tener dos botones de cierre en la misma
   * pantalla dejaría uno de los dos salteando la compuerta de §10.2.1 d.
   */
  onEficaciaChange?: (eficaz: boolean | null) => void;
}

/**
 * Etapas del tratamiento de un Registro de Mejora.
 *
 * Replica el flujo de la aplicacion del cliente: al abrir un registro se ve el
 * proceso completo, no una etapa suelta. Cada etapa lleva su propio
 * `Responsable Etapa` — quien efectivamente la ejecuto, que no siempre es a
 * quien se le asigno al registrar.
 */
export function EtapasMejoraPanel({ ncId, responsableOptions, flujoCorto = false, onEficaciaChange }: Props) {
  const htmlId = useId();
  const { nonConformities, updateEtapas } = useAudits();
  const nc = nonConformities.find((n) => n.id === ncId);
  const saved = nc?.etapasMejora;

  const [correccion, setCorreccion] = useState<EtapaCorreccion>(
    saved?.correccion ?? { correccionInmediata: '', evidenciaUrls: [] },
  );
  const [analisis, setAnalisis] = useState<EtapaAnalisisCausa>(
    saved?.analisisCausa ?? { metodologiaId: '', cincoPorques: ['', '', '', '', ''], causaRaiz: '' },
  );
  const [causasPescado, setCausasPescado] = useState<string[]>(
    saved?.analisisCausa?.espinaPescado?.causas.map((c) => c.texto) ?? ['', '', ''],
  );
  const [capa, setCapa] = useState<EtapaAccionCorrectiva>(
    saved?.accionCorrectiva ?? { severidad: 'Alta', tipoAccion: 'correctiva', descripcionAccion: '', evidenciaUrls: [] },
  );
  const [seguimiento, setSeguimiento] = useState<EtapaSeguimiento>(
    saved?.seguimiento ?? {
      eficaz: null, causaSeRepitio: null, cumplioProposito: null,
      requiereActualizarRiesgos: null, requiereCambiosSGC: null, requiereActualizarFoda: null,
      salidas: [], evidenciaUrls: [],
    },
  );
  const [guardado, setGuardado] = useState(false);

  useEffect(() => {
    if (saved?.seguimiento?.eficaz !== undefined) {
      onEficaciaChange?.(saved.seguimiento.eficaz);
    }
  }, []);

  const metodologia = METODOLOGIAS_ANALISIS_CAUSA.find((m) => m.id === analisis.metodologiaId);
  const cierreHabilitado = puedeCerrarse(seguimiento);
  const salidas = salidasComprometidas(seguimiento);

  function upsertSalida(tipo: TipoSalida, patch: Partial<SalidaTratamiento>) {
    const existentes = [...seguimiento.salidas];
    const idx = existentes.findIndex((s) => s.tipo === tipo);
    if (idx >= 0) {
      existentes[idx] = { ...existentes[idx], ...patch };
    } else {
      existentes.push({ tipo, descripcion: '', estado: 'pendiente', ...patch });
    }
    setSeguimiento({ ...seguimiento, salidas: existentes });
  }

  function handleSalidaEstado(tipo: TipoSalida, estado: SalidaTratamiento['estado']) {
    upsertSalida(tipo, { estado, ...(estado !== 'descartada' ? { justificacionDescarte: undefined } : {}) });
  }

  function handleSalidaJustificacion(tipo: TipoSalida, justificacion: string) {
    upsertSalida(tipo, { justificacionDescarte: justificacion });
  }

  function selectResponsable(valor: string | undefined, onChange: (v: string) => void, key: string) {
    return (
      <FormField label="Responsable Etapa" htmlFor={`${htmlId}-${key}`}>
        <select id={`${htmlId}-${key}`} className={INPUT} value={valor ?? ''} onChange={(e) => onChange(e.target.value)}>
          <option value="">Seleccione…</option>
          {responsableOptions.map((r) => (
            <option key={r.id} value={r.id}>
              {r.nombre}
            </option>
          ))}
        </select>
      </FormField>
    );
  }

  return (
    <section className="rounded-card border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-semibold text-slate-900">Etapas del tratamiento</h2>
      <p className="mt-1 text-sm text-slate-500">
        Cada etapa registra quién la ejecutó. El cierre exige eficacia verificada.
      </p>

      {!flujoCorto && (
        <>
          <fieldset className="mt-6 rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-semibold text-slate-800">
              Etapa de Corrección <span className="font-normal text-slate-500">· §10.2.1 a</span>
            </legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Corrección Inmediata" htmlFor={`${htmlId}-ci`}>
                <textarea
                  id={`${htmlId}-ci`}
                  rows={3}
                  className={AREA}
                  value={correccion.correccionInmediata}
                  onChange={(e) => setCorreccion({ ...correccion, correccionInmediata: e.target.value })}
                />
              </FormField>
              <FormField label="Fecha de Ejecución de Corrección" htmlFor={`${htmlId}-fec`}>
                <input
                  id={`${htmlId}-fec`}
                  type="date"
                  className={INPUT}
                  value={correccion.fechaEjecucion ?? ''}
                  onChange={(e) => setCorreccion({ ...correccion, fechaEjecucion: e.target.value })}
                />
              </FormField>
              <FormField label="Evidencia" htmlFor={`${htmlId}-evc`}>
                <textarea
                  id={`${htmlId}-evc`}
                  rows={2}
                  className={AREA}
                  value={correccion.evidencia ?? ''}
                  onChange={(e) => setCorreccion({ ...correccion, evidencia: e.target.value })}
                />
              </FormField>
              {selectResponsable(
                correccion.responsableEtapaId,
                (v) => setCorreccion({ ...correccion, responsableEtapaId: v }),
                'rc',
              )}
            </div>
          </fieldset>

          <fieldset className="mt-4 rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-semibold text-slate-800">
              Etapa de Análisis de Causa <span className="font-normal text-slate-500">· §10.2.1 b</span>
            </legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Metodología de Análisis de Causa" htmlFor={`${htmlId}-met`} required>
                <select
                  id={`${htmlId}-met`}
                  className={INPUT}
                  value={analisis.metodologiaId}
                  onChange={(e) => setAnalisis({ ...analisis, metodologiaId: e.target.value })}
                >
                  <option value="">Seleccione…</option>
                  {METODOLOGIAS_ANALISIS_CAUSA.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.nombre}
                    </option>
                  ))}
                </select>
              </FormField>
              {selectResponsable(
                analisis.responsableEtapaId,
                (v) => setAnalisis({ ...analisis, responsableEtapaId: v }),
                'ra',
              )}
            </div>

            {metodologia?.forma === 'cinco_porques' && (
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {analisis.cincoPorques.map((valor, i) => (
                  <FormField key={i} label={`Por Qué ${i + 1}`} htmlFor={`${htmlId}-pq${i}`}>
                    <textarea
                      id={`${htmlId}-pq${i}`}
                      rows={2}
                      className={AREA}
                      value={valor}
                      onChange={(e) => {
                        const copia = [...analisis.cincoPorques];
                        copia[i] = e.target.value;
                        setAnalisis({ ...analisis, cincoPorques: copia });
                      }}
                    />
                  </FormField>
                ))}
              </div>
            )}

            {metodologia?.forma === 'espina_pescado' && (
              <div className="mt-4">
                <p className="mb-2 text-sm text-slate-600">Causas identificadas</p>
                <div className="grid gap-3 sm:grid-cols-3">
                  {causasPescado.map((c, i) => (
                    <textarea
                      key={i}
                      aria-label={`Causa ${i + 1}`}
                      rows={3}
                      className={AREA}
                      placeholder="Causa"
                      value={c}
                      onChange={(e) => {
                        const copia = [...causasPescado];
                        copia[i] = e.target.value;
                        setCausasPescado(copia);
                        setAnalisis({
                          ...analisis,
                          espinaPescado: { causas: copia.filter((x) => x.trim()).map((texto) => ({ texto })) },
                        });
                      }}
                    />
                  ))}
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  className="mt-3"
                  onClick={() => setCausasPescado([...causasPescado, ''])}
                >
                  Agregar causa
                </Button>
              </div>
            )}

            <div className="mt-4">
              <FormField label="Causa Raíz" htmlFor={`${htmlId}-cr`}>
                <textarea
                  id={`${htmlId}-cr`}
                  rows={3}
                  className={AREA}
                  value={analisis.causaRaiz}
                  onChange={(e) => setAnalisis({ ...analisis, causaRaiz: e.target.value })}
                />
              </FormField>
            </div>
          </fieldset>
        </>
      )}

      <fieldset className="mt-4 rounded-lg border border-slate-200 p-4">
        <legend className="px-1 text-sm font-semibold text-slate-800">
          Etapa de Acción Correctiva <span className="font-normal text-slate-500">· §10.2.1 c</span>
        </legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Tipo de Severidad" htmlFor={`${htmlId}-sev`}>
            <select
              id={`${htmlId}-sev`}
              className={INPUT}
              value={capa.severidad}
              onChange={(e) => setCapa({ ...capa, severidad: e.target.value })}
            >
              <option value="Alta">Alta</option>
              <option value="Media">Media</option>
              <option value="Baja">Baja</option>
            </select>
          </FormField>
          <FormField label="Tipo Acción" htmlFor={`${htmlId}-ta`}>
            <select
              id={`${htmlId}-ta`}
              className={INPUT}
              value={capa.tipoAccion}
              onChange={(e) => setCapa({ ...capa, tipoAccion: e.target.value as 'correctiva' | 'preventiva' })}
            >
              <option value="correctiva">Correctiva</option>
              <option value="preventiva">Preventiva</option>
            </select>
          </FormField>
          <FormField label="Acción Correctiva" htmlFor={`${htmlId}-ac`}>
            <textarea
              id={`${htmlId}-ac`}
              rows={3}
              className={AREA}
              value={capa.descripcionAccion}
              onChange={(e) => setCapa({ ...capa, descripcionAccion: e.target.value })}
            />
          </FormField>
          <FormField label="Evidencia de la Acción" htmlFor={`${htmlId}-ea`}>
            <textarea
              id={`${htmlId}-ea`}
              rows={3}
              className={AREA}
              value={capa.evidenciaAccion ?? ''}
              onChange={(e) => setCapa({ ...capa, evidenciaAccion: e.target.value })}
            />
          </FormField>
          <FormField label="Fecha Inicial" htmlFor={`${htmlId}-fi`}>
            <input
              id={`${htmlId}-fi`}
              type="date"
              className={INPUT}
              value={capa.fechaInicial ?? ''}
              onChange={(e) => setCapa({ ...capa, fechaInicial: e.target.value })}
            />
          </FormField>
          <FormField label="Fecha Finalización" htmlFor={`${htmlId}-ff`}>
            <input
              id={`${htmlId}-ff`}
              type="date"
              className={INPUT}
              value={capa.fechaFinalizacion ?? ''}
              onChange={(e) => setCapa({ ...capa, fechaFinalizacion: e.target.value })}
            />
          </FormField>
          {selectResponsable(capa.responsableEtapaId, (v) => setCapa({ ...capa, responsableEtapaId: v }), 'rk')}
        </div>
      </fieldset>

      <fieldset className="mt-4 rounded-lg border border-slate-200 p-4">
        <legend className="px-1 text-sm font-semibold text-slate-800">
          Etapa de Seguimiento <span className="font-normal text-slate-500">· §10.2.1 d, e y f</span>
        </legend>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Eficacia" htmlFor={`${htmlId}-ef`}>
            <select
              id={`${htmlId}-ef`}
              className={INPUT}
              value={aSelect(seguimiento.eficaz)}
              onChange={(e) => {
                const valor = deSelect(e.target.value);
                setSeguimiento({ ...seguimiento, eficaz: valor });
                onEficaciaChange?.(valor);
              }}
            >
              <option value="">Seleccione…</option>
              <option value="NO">NO</option>
              <option value="SI">SI</option>
            </select>
          </FormField>
          <FormField label="Fecha Seguimiento" htmlFor={`${htmlId}-fs`}>
            <input
              id={`${htmlId}-fs`}
              type="date"
              className={INPUT}
              value={seguimiento.fechaSeguimiento ?? ''}
              onChange={(e) => setSeguimiento({ ...seguimiento, fechaSeguimiento: e.target.value })}
            />
          </FormField>
        </div>

        <div className="mt-4 flex flex-col gap-4">
          {PREGUNTAS_SEGUIMIENTO.map(({ campo, label, clausula }) => (
            <div key={campo} className="grid gap-2 sm:grid-cols-[1fr_10rem] sm:items-center">
              <label htmlFor={`${htmlId}-${campo}`} className="text-sm text-slate-700">
                {label}
                {clausula && <span className="ml-1 text-xs text-slate-400">{clausula}</span>}
              </label>
              <select
                id={`${htmlId}-${campo}`}
                className={INPUT}
                value={aSelect(seguimiento[campo] as boolean | null)}
                onChange={(e) => setSeguimiento({ ...seguimiento, [campo]: deSelect(e.target.value) })}
              >
                <option value="">Seleccione…</option>
                <option value="NO">NO</option>
                <option value="SI">SI</option>
              </select>
            </div>
          ))}
        </div>

        {salidas.length > 0 && (
          <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4">
            <p className="text-sm font-semibold text-amber-900">
              Salidas comprometidas por este tratamiento
            </p>
            <ul className="mt-2 flex flex-col gap-3">
              {salidas.map((tipo) => {
                const catalogo = SALIDAS_REGLAMENTARIAS.find((s) => s.value === tipo)!;
                const salidaExistente = seguimiento.salidas.find((s) => s.tipo === tipo);
                const estado = salidaExistente?.estado ?? 'pendiente';
                return (
                  <li key={tipo} className="rounded-md border border-amber-200 bg-white p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <span className="text-sm font-medium text-amber-900">{catalogo.label}</span>
                        <span className="block text-xs text-amber-800">{catalogo.descripcion}</span>
                      </div>
                      <select
                        className="h-8 rounded border border-amber-300 bg-amber-50 px-2 text-xs font-medium"
                        value={estado}
                        onChange={(e) => handleSalidaEstado(tipo, e.target.value as SalidaTratamiento['estado'])}
                      >
                        <option value="pendiente">Pendiente</option>
                        <option value="ejecutada">Ejecutada</option>
                        <option value="descartada">Descartada</option>
                      </select>
                    </div>
                    {estado === 'descartada' && (
                      <div className="mt-2">
                        <label className="text-xs font-medium text-amber-900">
                          Justificación del descarte (obligatoria)
                        </label>
                        <textarea
                          rows={2}
                          className="mt-1 w-full rounded border border-amber-300 p-2 text-xs"
                          placeholder="Explique por qué esta salida no aplica…"
                          value={salidaExistente?.justificacionDescarte ?? ''}
                          onChange={(e) => handleSalidaJustificacion(tipo, e.target.value)}
                        />
                      </div>
                    )}
                    {estado === 'ejecutada' && (
                      <p className="mt-1 text-xs text-green-700">Resuelta</p>
                    )}
                  </li>
                );
              })}
            </ul>
            {salidasPendientes(seguimiento).length > 0 && (
              <p className="mt-3 text-xs text-amber-800">
                {salidasPendientes(seguimiento).length} salida(s) pendiente(s).
              </p>
            )}
          </div>
        )}

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <FormField label="Evidencia Seguimiento" htmlFor={`${htmlId}-es`}>
            <textarea
              id={`${htmlId}-es`}
              rows={2}
              className={AREA}
              value={seguimiento.observaciones ?? ''}
              onChange={(e) => setSeguimiento({ ...seguimiento, observaciones: e.target.value })}
            />
          </FormField>
          {selectResponsable(
            seguimiento.responsableEtapaId,
            (v) => setSeguimiento({ ...seguimiento, responsableEtapaId: v }),
            'rs',
          )}
        </div>
      </fieldset>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button type="button" onClick={() => {
          updateEtapas(ncId, {
            correccion: flujoCorto ? undefined : correccion,
            analisisCausa: flujoCorto ? undefined : analisis,
            accionCorrectiva: capa,
            seguimiento,
          });
          setGuardado(true);
        }}>
          Guardar etapas
        </Button>
        {cierreHabilitado ? (
          <p className="text-sm text-green-700">
            Eficacia verificada. El cierre con firma queda habilitado más abajo.
          </p>
        ) : (
          <p className="text-sm text-slate-500">
            El cierre con firma se habilita cuando la eficacia se verifica como SI (§10.2.1 d).
          </p>
        )}
        {guardado && (
          <p role="status" className="text-sm text-green-700">
            Etapas guardadas.
          </p>
        )}
      </div>
    </section>
  );
}
