'use client';

import { useEffect, useId, useState } from 'react';
import {
  SALIDAS_REGLAMENTARIAS,
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
import { useSession } from '@/lib/session';
import {
  actualizarCompromiso,
  cargarCompromisos,
  comprometerSalida,
  type CompromisoApi,
} from '@/lib/compromisos';
import { usePersonasAsignables } from '@/lib/crm-etapas-store';
import { mensajeDeError } from '@/lib/api-client';
import {
  cargarCatalogos,
  cargarEtapas,
  cicloDesdeApi,
  consultarCierre,
  etapasCambiadas,
  guardarEtapa,
  iniciarCiclo,
  type CicloEnPantalla,
  type EstadoDeCierre,
  type EtapaApi,
  type Metodologia,
  type Severidad,
  type TipoEtapa,
} from '@/lib/etapas-mejora';

const INPUT = 'h-11 w-full rounded-lg border border-slate-300 px-3 text-sm';
const AREA = 'w-full rounded-lg border border-slate-300 p-3 text-sm';
const HINT_FECHA = 'Con fecha, la etapa queda completada.';

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

const NOMBRE_ETAPA: Record<string, string> = {
  correccion: 'corrección',
  analisis_causa: 'análisis de causa',
  accion_correctiva: 'acción correctiva',
  seguimiento: 'seguimiento',
};

interface Props {
  ncId: string;
  /** Personas **de la base** (`/users/`): el responsable es una clave foránea. */
  responsableOptions: { id: string; nombre: string }[];
  /**
   * Lo que el servidor dice del cierre, después de cada carga y cada guardado.
   *
   * El cierre NO vive en este panel: vive en el bloque de Cierre con firma.
   * Y lo que sube es la respuesta de `puede-cerrarse`, **no lo que hay escrito
   * en el formulario**: marcar "SI" sin guardar no habilita nada.
   */
  onCierreChange?: (estado: EstadoDeCierre | null) => void;
}

/**
 * Etapas del tratamiento de un Registro de Mejora, contra `improvement_stage_entries`.
 *
 * Replica el flujo de la aplicacion del cliente: al abrir un registro se ve el
 * proceso completo, no una etapa suelta. Cada etapa lleva su propio
 * `Responsable Etapa` — quien efectivamente la ejecuto.
 *
 * **Qué etapas se muestran lo decide la base**, no el tipo del registro en el
 * navegador: un riesgo u oportunidad nace con tres filas y la pantalla dibuja
 * las que existen.
 */
/**
 * Una salida comprometida: quién la hace, para cuándo, y cómo quedó.
 *
 * La justificación se guarda al salir del campo y no en cada tecla: cada
 * cambio es una petición.
 */
function FilaDeCompromiso({
  compromiso,
  personas,
  onCambiar,
}: {
  compromiso: CompromisoApi;
  personas: { id: string; nombre: string }[];
  onCambiar: (cuerpo: Record<string, unknown>) => void;
}) {
  const catalogo = SALIDAS_REGLAMENTARIAS.find((s) => s.value === compromiso.kind);
  const [justificacion, setJustificacion] = useState(compromiso.justificacion ?? '');

  return (
    <li className="rounded-md border border-amber-200 bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <span className="text-sm font-medium text-amber-900">{catalogo?.label ?? compromiso.kind}</span>
          <span className="block text-xs text-amber-800">{catalogo?.descripcion ?? compromiso.descripcion}</span>
        </div>
        <select
          aria-label={`Estado de ${catalogo?.label ?? compromiso.kind}`}
          className="h-8 rounded border border-amber-300 bg-amber-50 px-2 text-xs font-medium"
          value={compromiso.status}
          onChange={(e) => {
            const nuevo = e.target.value;
            // Descartar exige el motivo: se manda junto, o la API lo rechaza.
            if (nuevo === 'descartada' && !justificacion.trim()) {
              setJustificacion('');
              onCambiar({ status: 'pendiente' });
              return;
            }
            onCambiar(nuevo === 'descartada' ? { status: nuevo, justificacion } : { status: nuevo });
          }}
        >
          <option value="pendiente">Pendiente</option>
          <option value="ejecutada">Ejecutada</option>
          <option value="descartada">Descartada</option>
        </select>
      </div>

      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <label className="text-xs font-medium text-amber-900">
          Responsable
          <select
            className="mt-1 h-8 w-full rounded border border-amber-300 px-2 text-xs"
            value={compromiso.responsable_user_id ?? ''}
            onChange={(e) => onCambiar({ responsable_user_id: e.target.value || null })}
          >
            <option value="">Sin asignar</option>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-amber-900">
          Fecha comprometida
          <input
            type="date"
            className="mt-1 h-8 w-full rounded border border-amber-300 px-2 text-xs"
            value={compromiso.due_date ?? ''}
            onChange={(e) => onCambiar({ due_date: e.target.value || null })}
          />
        </label>
      </div>

      {compromiso.status === 'descartada' || justificacion ? (
        <div className="mt-2">
          <label className="text-xs font-medium text-amber-900" htmlFor={`just-${compromiso.id}`}>
            Justificación del descarte (obligatoria)
          </label>
          <textarea
            id={`just-${compromiso.id}`}
            rows={2}
            className="mt-1 w-full rounded border border-amber-300 p-2 text-xs"
            placeholder="Explique por qué esta salida no aplica…"
            value={justificacion}
            onChange={(e) => setJustificacion(e.target.value)}
            onBlur={() => {
              if ((compromiso.justificacion ?? '') !== justificacion) onCambiar({ justificacion });
            }}
          />
        </div>
      ) : null}

      {compromiso.status === 'pendiente' && (compromiso.responsable_user_id === null || compromiso.due_date === null) && (
        <p className="mt-2 text-xs text-amber-800">
          Sin responsable o sin fecha no se le avisa a nadie: el registro no se cierra así.
        </p>
      )}
    </li>
  );
}

export function EtapasMejoraPanel({ ncId, responsableOptions, onCierreChange }: Props) {
  const htmlId = useId();
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;

  const [filas, setFilas] = useState<EtapaApi[] | null>(null);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const [metodologias, setMetodologias] = useState<Metodologia[]>([]);
  const [severidades, setSeveridades] = useState<Severidad[]>([]);
  const [ciclo, setCiclo] = useState<CicloEnPantalla>({});
  const [causasPescado, setCausasPescado] = useState<string[]>(['', '', '']);
  const [guardando, setGuardando] = useState(false);
  // Las salidas comprometidas viven en el servidor: ver `lib/compromisos.ts`.
  const [compromisos, setCompromisos] = useState<CompromisoApi[] | null>(null);
  const { personas } = usePersonasAsignables();
  const [resultado, setResultado] = useState<{ ok: boolean; texto: string } | null>(null);

  function adoptar(nuevas: EtapaApi[]) {
    setFilas(nuevas);
    const c = cicloDesdeApi(nuevas);
    setCiclo(c);
    const causas = c.analisisCausa?.espinaPescado?.causas.map((x) => x.texto) ?? [];
    setCausasPescado(causas.length > 0 ? causas : ['', '', '']);
  }

  async function refrescarCompromisos() {
    if (!tenantId) return;
    try {
      setCompromisos(await cargarCompromisos(ncId, tenantId));
    } catch {
      // `null` = no se pudo preguntar. La seccion lo dice en vez de mostrar
      // una lista vacia, que se leeria como "no hay nada comprometido".
      setCompromisos(null);
    }
  }

  async function comprometerLaFodaSiCorresponde() {
    if (!tenantId || ciclo.seguimiento?.requiereActualizarFoda !== true) return;
    if ((compromisos ?? []).some((c) => c.kind === 'matriz_foda')) return;
    try {
      await comprometerSalida(ncId, { kind: 'matriz_foda' }, tenantId);
    } catch {
      // Ya comprometida (409) o la API no respondio: lo dice el refresco.
    }
  }

  async function cambiarCompromiso(id: string, cuerpo: Record<string, unknown>) {
    if (!tenantId) return;
    try {
      await actualizarCompromiso(id, cuerpo, tenantId);
      await refrescarCompromisos();
      await refrescarCierre();
    } catch (e) {
      setResultado({ ok: false, texto: `No se pudo guardar la salida: ${mensajeDeError(e)}` });
    }
  }

  async function refrescarCierre() {
    if (!tenantId) return;
    try {
      onCierreChange?.(await consultarCierre(ncId, tenantId));
    } catch {
      // Sin respuesta no se habilita: `null` deja el cierre en "comprobando".
      onCierreChange?.(null);
    }
  }

  useEffect(() => {
    if (!tenantId) return;
    let vigente = true;
    setErrorDeCarga(null);
    Promise.all([cargarEtapas(ncId, tenantId), cargarCatalogos(tenantId)])
      .then(([etapas, catalogos]) => {
        if (!vigente) return;
        adoptar(etapas);
        setMetodologias(catalogos.metodologias);
        setSeveridades(catalogos.severidades);
      })
      .catch((e) => { if (vigente) setErrorDeCarga(mensajeDeError(e)); });
    void refrescarCierre();
    void refrescarCompromisos();
    return () => { vigente = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ncId, tenantId]);

  const { correccion, analisisCausa: analisis, accionCorrectiva: capa, seguimiento } = ciclo;
  const setCorreccion = (v: EtapaCorreccion) => setCiclo((c) => ({ ...c, correccion: v }));
  const setAnalisis = (v: EtapaAnalisisCausa) => setCiclo((c) => ({ ...c, analisisCausa: v }));
  const setCapa = (v: EtapaAccionCorrectiva) => setCiclo((c) => ({ ...c, accionCorrectiva: v }));
  const setSeguimiento = (v: EtapaSeguimiento) => setCiclo((c) => ({ ...c, seguimiento: v }));

  const metodologia = metodologias.find((m) => m.id === analisis?.metodologiaId);
  const salidas = seguimiento ? salidasComprometidas(seguimiento) : [];

  function upsertSalida(tipo: TipoSalida, patch: Partial<SalidaTratamiento>) {
    if (!seguimiento) return;
    const existentes = [...seguimiento.salidas];
    const idx = existentes.findIndex((s) => s.tipo === tipo);
    if (idx >= 0) existentes[idx] = { ...existentes[idx], ...patch };
    else existentes.push({ tipo, descripcion: '', estado: 'pendiente', ...patch });
    setSeguimiento({ ...seguimiento, salidas: existentes });
  }

  async function handleIniciar() {
    if (!tenantId) return;
    setGuardando(true);
    try {
      adoptar(await iniciarCiclo(ncId, tenantId));
      await refrescarCierre();
    } catch (e) {
      setResultado({ ok: false, texto: `No se crearon las etapas: ${mensajeDeError(e)}` });
    } finally {
      setGuardando(false);
    }
  }

  async function handleGuardar() {
    if (!tenantId || !filas) return;
    const pendientes = etapasCambiadas(filas, ciclo);
    if (pendientes.length === 0) {
      setResultado({ ok: true, texto: 'No hay cambios que guardar.' });
      return;
    }
    setGuardando(true);
    setResultado(null);
    let actuales = filas;
    const fallidas: string[] = [];
    try {
      // **Se intentan todas**, y no se corta en la primera que falla: que el
      // responsable de una etapa sea inválido no es razón para perder lo
      // escrito en las otras. Las guardadas se adoptan; las que fallaron
      // conservan lo escrito para reintentar, y se dice cuántas y cuáles.
      for (const { etapa, cuerpo } of pendientes) {
        try {
          const guardada = await guardarEtapa(ncId, etapa.id, cuerpo, tenantId);
          actuales = actuales.map((f) => (f.id === guardada.id ? guardada : f));
        } catch (e) {
          fallidas.push(`${NOMBRE_ETAPA[etapa.kind] ?? etapa.kind} (${mensajeDeError(e)})`);
        }
      }
      if (fallidas.length === 0) {
        adoptar(actuales);
        // La FODA no sale de una casilla de la base: la compromete la pantalla.
        // Las otras dos las crea la API al guardar el seguimiento.
        await comprometerLaFodaSiCorresponde();
        await refrescarCompromisos();
        setResultado({ ok: true, texto: 'Etapas guardadas.' });
      } else {
        // Solo `filas`: el formulario se queda con lo escrito, así que al volver
        // a guardar se mandan únicamente las que fallaron.
        setFilas(actuales);
        setResultado({
          ok: false,
          texto: `No se guardaron ${fallidas.length} de ${pendientes.length} etapas: ${fallidas.join('; ')}.`,
        });
      }
    } finally {
      setGuardando(false);
      await refrescarCierre();
    }
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

  function campoLimite(kind: TipoEtapa) {
    return (
      <FormField
        label="Fecha límite"
        htmlFor={`${htmlId}-lim-${kind}`}
        hint="Con fecha límite, el responsable recibe avisos antes de que venza."
      >
        <input
          id={`${htmlId}-lim-${kind}`}
          type="date"
          className={INPUT}
          value={ciclo.limites?.[kind] ?? ''}
          onChange={(e) => setCiclo((c) => ({ ...c, limites: { ...c.limites, [kind]: e.target.value } }))}
        />
      </FormField>
    );
  }

  function estadoEtapa(kind: string) {
    const fila = filas?.find((f) => f.kind === kind);
    if (!fila) return null;
    return fila.completada_en ? (
      <span className="ml-2 rounded-full bg-semaforo-cumple-bg px-2 py-0.5 text-xs font-medium text-semaforo-cumple">Completada</span>
    ) : (
      <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
        Pendiente{fila.due_date ? ` · vence ${fila.due_date}` : ''}
      </span>
    );
  }

  const encabezado = (
    <>
      <h2 className="text-lg font-semibold text-slate-900">Etapas del tratamiento</h2>
      <p className="mt-1 text-sm text-slate-500">
        Cada etapa registra quién la ejecutó y cuándo. El cierre exige todas completadas y la eficacia verificada.
      </p>
    </>
  );

  if (errorDeCarga) {
    return (
      <section className="rounded-card border border-slate-200 bg-white p-6">
        {encabezado}
        <p className="mt-4 text-sm text-semaforo-no-cumple">No se pudieron cargar las etapas: {errorDeCarga}</p>
      </section>
    );
  }

  if (filas === null) {
    return (
      <section className="rounded-card border border-slate-200 bg-white p-6">
        {encabezado}
        <p className="mt-4 text-sm text-slate-500">Cargando etapas…</p>
      </section>
    );
  }

  if (filas.length === 0) {
    // Registros anteriores al 12-sep: nacieron sin ciclo tipado. Siguen
    // cerrándose con la regla anterior (un plan de acción verificado) hasta
    // que alguien decida iniciarlo — y entonces rige el ciclo completo.
    return (
      <section className="rounded-card border border-slate-200 bg-white p-6">
        {encabezado}
        <p className="mt-4 text-sm text-slate-600">
          Este registro es anterior al ciclo de etapas y no tiene ninguna. Se cierra con la regla anterior: al menos un plan de acción verificado.
        </p>
        <Button type="button" variant="secondary" className="mt-3" onClick={handleIniciar} disabled={guardando}>
          Iniciar ciclo de etapas
        </Button>
        {resultado && !resultado.ok && <p className="mt-2 text-sm text-semaforo-no-cumple">{resultado.texto}</p>}
      </section>
    );
  }

  return (
    <section className="rounded-card border border-slate-200 bg-white p-6">
      {encabezado}

      {correccion && (
        <fieldset className="mt-6 rounded-lg border border-slate-200 p-4">
          <legend className="px-1 text-sm font-semibold text-slate-800">
            Etapa de Corrección <span className="font-normal text-slate-500">· §10.2.1 a</span>
            {estadoEtapa('correccion')}
          </legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Corrección Inmediata" htmlFor={`${htmlId}-ci`}>
              <textarea id={`${htmlId}-ci`} rows={3} className={AREA} value={correccion.correccionInmediata}
                onChange={(e) => setCorreccion({ ...correccion, correccionInmediata: e.target.value })} />
            </FormField>
            <FormField label="Fecha de Ejecución de Corrección" htmlFor={`${htmlId}-fec`} hint={HINT_FECHA}>
              <input id={`${htmlId}-fec`} type="date" className={INPUT} value={correccion.fechaEjecucion ?? ''}
                onChange={(e) => setCorreccion({ ...correccion, fechaEjecucion: e.target.value })} />
            </FormField>
            <FormField label="Evidencia" htmlFor={`${htmlId}-evc`}>
              <textarea id={`${htmlId}-evc`} rows={2} className={AREA} value={correccion.evidencia ?? ''}
                onChange={(e) => setCorreccion({ ...correccion, evidencia: e.target.value })} />
            </FormField>
            {selectResponsable(correccion.responsableEtapaId, (v) => setCorreccion({ ...correccion, responsableEtapaId: v }), 'rc')}
            {campoLimite('correccion')}
          </div>
        </fieldset>
      )}

      {analisis && (
        <fieldset className="mt-4 rounded-lg border border-slate-200 p-4">
          <legend className="px-1 text-sm font-semibold text-slate-800">
            Etapa de Análisis de Causa <span className="font-normal text-slate-500">· §10.2.1 b</span>
            {estadoEtapa('analisis_causa')}
          </legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Metodología de Análisis de Causa" htmlFor={`${htmlId}-met`} required>
              <select id={`${htmlId}-met`} className={INPUT} value={analisis.metodologiaId}
                onChange={(e) => setAnalisis({ ...analisis, metodologiaId: e.target.value })}>
                <option value="">Seleccione…</option>
                {metodologias.map((m) => (
                  <option key={m.id} value={m.id}>{m.nombre}</option>
                ))}
              </select>
            </FormField>
            <FormField label="Fecha de Ejecución del Análisis" htmlFor={`${htmlId}-fea`} hint={HINT_FECHA}>
              <input id={`${htmlId}-fea`} type="date" className={INPUT} value={analisis.fechaEjecucion ?? ''}
                onChange={(e) => setAnalisis({ ...analisis, fechaEjecucion: e.target.value })} />
            </FormField>
            {selectResponsable(analisis.responsableEtapaId, (v) => setAnalisis({ ...analisis, responsableEtapaId: v }), 'ra')}
            {campoLimite('analisis_causa')}
          </div>

          {metodologia?.forma === 'cinco_porques' && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {analisis.cincoPorques.map((valor, i) => (
                <FormField key={i} label={`Por Qué ${i + 1}`} htmlFor={`${htmlId}-pq${i}`}>
                  <textarea id={`${htmlId}-pq${i}`} rows={2} className={AREA} value={valor}
                    onChange={(e) => {
                      const copia = [...analisis.cincoPorques];
                      copia[i] = e.target.value;
                      setAnalisis({ ...analisis, cincoPorques: copia });
                    }} />
                </FormField>
              ))}
            </div>
          )}

          {metodologia?.forma === 'espina_pescado' && (
            <div className="mt-4">
              <p className="mb-2 text-sm text-slate-600">Causas identificadas</p>
              <div className="grid gap-3 sm:grid-cols-3">
                {causasPescado.map((c, i) => (
                  <textarea key={i} aria-label={`Causa ${i + 1}`} rows={3} className={AREA} placeholder="Causa" value={c}
                    onChange={(e) => {
                      const copia = [...causasPescado];
                      copia[i] = e.target.value;
                      setCausasPescado(copia);
                      setAnalisis({
                        ...analisis,
                        espinaPescado: { causas: copia.filter((x) => x.trim()).map((texto) => ({ texto })) },
                      });
                    }} />
                ))}
              </div>
              <Button type="button" variant="secondary" className="mt-3" onClick={() => setCausasPescado([...causasPescado, ''])}>
                Agregar causa
              </Button>
            </div>
          )}

          <div className="mt-4">
            <FormField label="Causa Raíz" htmlFor={`${htmlId}-cr`}>
              <textarea id={`${htmlId}-cr`} rows={3} className={AREA} value={analisis.causaRaiz}
                onChange={(e) => setAnalisis({ ...analisis, causaRaiz: e.target.value })} />
            </FormField>
          </div>
        </fieldset>
      )}

      {capa && (
        <fieldset className="mt-4 rounded-lg border border-slate-200 p-4">
          <legend className="px-1 text-sm font-semibold text-slate-800">
            Etapa de Acción Correctiva <span className="font-normal text-slate-500">· §10.2.1 c</span>
            {estadoEtapa('accion_correctiva')}
          </legend>
          <div className="grid gap-4 sm:grid-cols-2">
            {/* La escala sale del catálogo de la empresa. Antes era "Alta/Media/
                Baja" escrita acá, que no coincidía con ninguna severidad de la base. */}
            <FormField label="Tipo de Severidad" htmlFor={`${htmlId}-sev`}>
              <select id={`${htmlId}-sev`} className={INPUT} value={capa.severidad}
                onChange={(e) => setCapa({ ...capa, severidad: e.target.value })}>
                <option value="">Seleccione…</option>
                {severidades.map((s) => (
                  <option key={s.code} value={s.code}>{s.label}</option>
                ))}
              </select>
            </FormField>
            <FormField label="Tipo Acción" htmlFor={`${htmlId}-ta`}>
              <select id={`${htmlId}-ta`} className={INPUT} value={capa.tipoAccion}
                onChange={(e) => setCapa({ ...capa, tipoAccion: e.target.value as 'correctiva' | 'preventiva' })}>
                <option value="correctiva">Correctiva</option>
                <option value="preventiva">Preventiva</option>
              </select>
            </FormField>
            <FormField label="Acción Correctiva" htmlFor={`${htmlId}-ac`}>
              <textarea id={`${htmlId}-ac`} rows={3} className={AREA} value={capa.descripcionAccion}
                onChange={(e) => setCapa({ ...capa, descripcionAccion: e.target.value })} />
            </FormField>
            <FormField label="Evidencia de la Acción" htmlFor={`${htmlId}-ea`}>
              <textarea id={`${htmlId}-ea`} rows={3} className={AREA} value={capa.evidenciaAccion ?? ''}
                onChange={(e) => setCapa({ ...capa, evidenciaAccion: e.target.value })} />
            </FormField>
            <FormField label="Fecha Inicial" htmlFor={`${htmlId}-fi`}>
              <input id={`${htmlId}-fi`} type="date" className={INPUT} value={capa.fechaInicial ?? ''}
                onChange={(e) => setCapa({ ...capa, fechaInicial: e.target.value })} />
            </FormField>
            <FormField label="Fecha Finalización" htmlFor={`${htmlId}-ff`} hint={HINT_FECHA}>
              <input id={`${htmlId}-ff`} type="date" className={INPUT} value={capa.fechaFinalizacion ?? ''}
                onChange={(e) => setCapa({ ...capa, fechaFinalizacion: e.target.value })} />
            </FormField>
            {selectResponsable(capa.responsableEtapaId, (v) => setCapa({ ...capa, responsableEtapaId: v }), 'rk')}
            {campoLimite('accion_correctiva')}
          </div>
        </fieldset>
      )}

      {seguimiento && (
        <fieldset className="mt-4 rounded-lg border border-slate-200 p-4">
          <legend className="px-1 text-sm font-semibold text-slate-800">
            Etapa de Seguimiento <span className="font-normal text-slate-500">· §10.2.1 d, e y f</span>
            {estadoEtapa('seguimiento')}
          </legend>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Eficacia" htmlFor={`${htmlId}-ef`}>
              <select id={`${htmlId}-ef`} className={INPUT} value={aSelect(seguimiento.eficaz)}
                onChange={(e) => setSeguimiento({ ...seguimiento, eficaz: deSelect(e.target.value) })}>
                <option value="">Seleccione…</option>
                <option value="NO">NO</option>
                <option value="SI">SI</option>
              </select>
            </FormField>
            <FormField label="Fecha Seguimiento" htmlFor={`${htmlId}-fs`} hint={HINT_FECHA}>
              <input id={`${htmlId}-fs`} type="date" className={INPUT} value={seguimiento.fechaSeguimiento ?? ''}
                onChange={(e) => setSeguimiento({ ...seguimiento, fechaSeguimiento: e.target.value })} />
            </FormField>
          </div>

          <div className="mt-4 flex flex-col gap-4">
            {PREGUNTAS_SEGUIMIENTO.map(({ campo, label, clausula }) => (
              <div key={campo} className="grid gap-2 sm:grid-cols-[1fr_10rem] sm:items-center">
                <label htmlFor={`${htmlId}-${campo}`} className="text-sm text-slate-700">
                  {label}
                  {clausula && <span className="ml-1 text-xs text-slate-400">{clausula}</span>}
                </label>
                <select id={`${htmlId}-${campo}`} className={INPUT} value={aSelect(seguimiento[campo] as boolean | null)}
                  onChange={(e) => setSeguimiento({ ...seguimiento, [campo]: deSelect(e.target.value) })}>
                  <option value="">Seleccione…</option>
                  <option value="NO">NO</option>
                  <option value="SI">SI</option>
                </select>
              </div>
            ))}
          </div>

          {(compromisos === null || compromisos.length > 0 || salidas.length > 0) && (
            <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4">
              <p className="text-sm font-semibold text-amber-900">Salidas comprometidas por este tratamiento</p>
              {compromisos === null ? (
                <p className="mt-2 text-xs text-amber-800" role="alert">
                  No se pudieron cargar las salidas comprometidas. Sin eso no se sabe qué quedó pendiente.
                </p>
              ) : compromisos.length === 0 ? (
                <p className="mt-2 text-xs text-amber-800">
                  Se comprometen al guardar: lo que marques «SI» queda con responsable y plazo, y sigue
                  a la vista aunque el registro se cierre.
                </p>
              ) : (
                <ul className="mt-2 flex flex-col gap-3">
                  {compromisos.map((c) => (
                    <FilaDeCompromiso
                      key={c.id}
                      compromiso={c}
                      personas={personas}
                      onCambiar={(cuerpo) => cambiarCompromiso(c.id, cuerpo)}
                    />
                  ))}
                </ul>
              )}
              {compromisos !== null && compromisos.some((c) => c.status === 'pendiente') && (
                <p className="mt-3 text-xs text-amber-800">
                  {compromisos.filter((c) => c.status === 'pendiente').length} salida(s) pendiente(s).
                </p>
              )}
            </div>
          )}

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <FormField label="Evidencia Seguimiento" htmlFor={`${htmlId}-es`}>
              <textarea id={`${htmlId}-es`} rows={2} className={AREA} value={seguimiento.observaciones ?? ''}
                onChange={(e) => setSeguimiento({ ...seguimiento, observaciones: e.target.value })} />
            </FormField>
            {selectResponsable(seguimiento.responsableEtapaId, (v) => setSeguimiento({ ...seguimiento, responsableEtapaId: v }), 'rs')}
            {campoLimite('seguimiento')}
          </div>
        </fieldset>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button type="button" onClick={handleGuardar} disabled={guardando}>
          {guardando ? 'Guardando…' : 'Guardar etapas'}
        </Button>
        {resultado && (
          <p role="status" className={resultado.ok ? 'text-sm text-green-700' : 'text-sm text-semaforo-no-cumple'}>
            {resultado.texto}
          </p>
        )}
      </div>
    </section>
  );
}
