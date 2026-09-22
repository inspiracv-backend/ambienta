'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Audit, NonConformity, TipoRegistroMejora } from '@ambienta/shared';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useUsers } from '@/lib/users-store';
import { useSession } from '@/lib/session';
import { CRITICIDAD_LABEL, NC_ESTADO_LABEL } from '@/lib/audit-status';
import { api, mensajeDeError } from '@/lib/api-client';
import { useToast } from '@/lib/toast-store';

interface AuditsContextValue {
  audits: Audit[];
  nonConformities: NonConformity[];
  loading: boolean;
  /**
   * Por que la lista esta vacia, si es que fallo (#208).
   *
   * `null` = se pregunto y esto es lo que hay. Un texto = **no se pudo
   * preguntar**, y la pantalla tiene que decirlo: sin esto un fallo de red se
   * ve igual que "esta empresa no tiene ninguno".
   */
  errorDeCarga: string | null;
  /** Rechaza si la base no lo creó; devuelve el registro con el id real. */
  addNonConformity: (input: {
    tenantId: string;
    plantId: string;
    hallazgo: string;
    severidad: string;
    responsableId: string;
    tipoRegistro?: TipoRegistroMejora;
    origen?: string;
    auditItemId?: string;
    productData?: Record<string, string>;
    complaintData?: Record<string, string>;
  }) => Promise<NonConformity>;
  updatePorques: (ncId: string, cincoPorques: string[]) => void;
  closeNonConformity: (ncId: string, responsableId: string) => void;
  /** Suma a la lista la auditoría que la API acaba de crear, con su id real. */
  agregarAuditoria: (raw: Record<string, unknown>) => Audit | null;
  /** Refleja en la lista el estado que la API confirmó (`planned`, `active`, ...). */
  actualizarEstadoAuditoria: (auditId: string, statusDeLaApi: string) => void;
}

const AuditsContext = createContext<AuditsContextValue | null>(null);

/** `audits.audit_type` de la API → los dos tipos del modelo compartido. */
const TIPO_POR_AUDIT_TYPE: Record<string, Audit['tipo']> = {
  internal: 'interna',
  external: 'externa',
  // La API admite tambien 'regulatory' y 'supplier'. El modelo compartido solo
  // distingue interna/externa, asi que ambas caen en externa: las hace un
  // tercero. Si el negocio necesita separarlas, se amplia AuditSchema.
  regulatory: 'externa',
  supplier: 'externa',
};

/** `audits.status` de la API → los tres estados del modelo compartido. */
const ESTADO_POR_STATUS: Record<string, Audit['estado']> = {
  planned: 'planificada',
  active: 'en_curso',
  reporting: 'en_curso',
  closed: 'cerrada',
  // Cancelada no es cerrada: una no entrego resultado y la otra si.
  cancelled: 'cancelada',
};

/**
 * `nonconformities.severity` de la API ↔ la criticidad del modelo compartido.
 *
 * La base restringe la columna a `minor|major|critical`. El alta mandaba
 * directamente `'alta'`, que viola ese CHECK: la fila nunca se insertaba y el
 * `.catch(() => {})` se comia el error, asi que la pantalla mostraba el
 * hallazgo creado y la base no tenia nada.
 */
const CRITICIDAD_POR_SEVERITY: Record<string, NonConformity['criticidad']> = {
  minor: 'baja',
  major: 'media',
  critical: 'alta',
};
const SEVERITY_POR_CRITICIDAD: Record<NonConformity['criticidad'], string> = {
  baja: 'minor',
  media: 'major',
  alta: 'critical',
};

/**
 * `nonconformities.status` de la API → los tres estados de la pantalla.
 *
 * La base modela seis estados y el frontend tres. Las tres etapas intermedias
 * —analisis, plan de accion y verificacion— son todas "en tratamiento" para
 * quien mira la lista. `rejected` cae en cerrada: no sigue abierta, y mostrarla
 * como pendiente inflaria el conteo de lo que falta resolver.
 */
const NC_ESTADO_POR_STATUS: Record<string, NonConformity['estado']> = {
  open: 'abierta',
  analysis: 'en_tratamiento',
  action_plan: 'en_tratamiento',
  verification: 'en_tratamiento',
  closed: 'cerrada',
  rejected: 'cerrada',
};

/** El estado que le corresponde en la API a una que pasa a tratamiento. */
const STATUS_EN_TRATAMIENTO = 'analysis';

function mapApiNonConformity(raw: Record<string, unknown>): NonConformity | null {
  try {
    const cerradaEl = raw.closed_at ? String(raw.closed_at) : null;
    const responsableId = raw.owner_user_id ? String(raw.owner_user_id) : '';
    return {
      id: String(raw.id),
      tenantId: String(raw.tenant_id ?? ''),
      // `facility_id` es opcional en la base: hay hallazgos de la empresa que
      // no cuelgan de una planta. La pantalla filtra por planta, asi que la
      // cadena vacia los deja fuera de esos filtros en vez de asignarlos mal.
      plantId: raw.facility_id ? String(raw.facility_id) : '',
      hallazgo: String(raw.description ?? raw.title ?? ''),
      criticidad: CRITICIDAD_POR_SEVERITY[String(raw.severity ?? '')] ?? 'media',
      estado: NC_ESTADO_POR_STATUS[String(raw.status ?? '')] ?? 'abierta',
      fechaDeteccion: String(raw.detected_at ?? new Date().toISOString()),
      responsableId,
      // Ambos vienen como JSONB. Se validan de forma: un `{}` donde se espera
      // una lista rompe la pantalla de los 5 porques al renderizar.
      cincoPorques: Array.isArray(raw.root_cause_answers)
        ? (raw.root_cause_answers as unknown[]).map(String).slice(0, 5)
        : [],
      // `improvement_stages` (JSONB) ya no se lee: las etapas se piden aparte a
      // `/nonconformities/{id}/etapas`, que es lo que el cierre comprueba.
      ...(raw.record_type ? { tipoRegistro: String(raw.record_type) as TipoRegistroMejora } : {}),
      ...(raw.audit_item_id ? { auditItemId: String(raw.audit_item_id) } : {}),
      // La API no expone el `audit_id` en el listado, solo `audit_item_id`. Se
      // deja sin origen antes que inventar el vinculo.
      ...(cerradaEl
        ? { cierre: { fecha: cerradaEl, responsableId, firmada: true } }
        : {}),
    };
  } catch {
    return null;
  }
}

function mapApiAudit(raw: Record<string, unknown>): Audit | null {
  try {
    return {
      id: String(raw.id),
      tenantId: String(raw.tenant_id ?? ''),
      plantId: String(raw.facility_id ?? ''),
      tipo: TIPO_POR_AUDIT_TYPE[String(raw.audit_type ?? '')] ?? 'interna',
      // **Sin fecha planificada no se inventa la de hoy.** Antes una auditoría
      // sin `planned_start` aparecía fechada el día en que se abría la pantalla,
      // distinto cada día. Vacío se muestra como "Sin fecha".
      fecha: raw.planned_start ? String(raw.planned_start) : '',
      estado: ESTADO_POR_STATUS[String(raw.status ?? '')] ?? 'planificada',
      // La API los tiene como `scope` (texto libre) y en tablas aparte; el
      // listado no los trae. Se pueblan al abrir el detalle.
      procesos: [],
      normativaIds: [],
      ...(raw.code ? { codigo: String(raw.code) } : {}),
      ...(raw.title ? { titulo: String(raw.title) } : {}),
    };
  } catch {
    return null;
  }
}

export function AuditsProvider({ children }: { children: ReactNode }) {
  const [audits, setAudits] = useState<Audit[]>([]);
  const [nonConformities, setNonConformities] = useState<NonConformity[]>([]);
  const [loading, setLoading] = useState(true);
  const [datosDe, setDatosDe] = useState<string | null>(null);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const registrar = useRegistrarAuditoria();
  const { users } = useUsers();
  const { user } = useSession();
  const { mostrarToast } = useToast();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    Promise.all([
      api.get<Record<string, unknown>[]>('/audits/', { tenantId: user.tenantId }),
      api.get<Record<string, unknown>[]>('/audits/nonconformities/', { tenantId: user.tenantId }),
    ])
      .then(([auditsData, ncData]) => {
        if (cancelled) return;
        const mappedAudits = auditsData.map(mapApiAudit).filter((a): a is Audit => a !== null);
        // **Se escribe siempre, incluso vacio** (#208). El `if (length > 0)`
        // de antes no distinguia dos cosas muy distintas: que la API fallara
        // —donde quedarse con lo que hay es un respaldo razonable— y que
        // respondiera **cero filas**, donde quedarse con los datos de ejemplo
        // es mostrar algo que no existe.
        //
        // El `catch` sigue conservando lo ultimo conocido, asi que trabajar sin
        // backend levantado sigue funcionando: ahi la peticion falla, no
        // devuelve vacio.
        setAudits(mappedAudits);
        const mappedNc = ncData
          .map(mapApiNonConformity)
          .filter((n): n is NonConformity => n !== null);
        setNonConformities(mappedNc);
      })
      .catch((e: unknown) => {
        // **Se dice que fallo.** Con la lista vacia y sin mensaje, la
        // pantalla afirma 'no hay nada' cuando la verdad es 'no se pudo
        // preguntar' — que es la misma mentira de #208 en su otra forma.
        setErrorDeCarga(mensajeDeError(e));
      })
      .finally(() => { if (!cancelled) { setLoading(false); setDatosDe(user?.tenantId ?? null); } });
    return () => { cancelled = true; };
  }, [user?.tenantId]);

  function etiqueta(nc: NonConformity): string {
    return nc.hallazgo.length > 70 ? `${nc.hallazgo.slice(0, 70)}…` : nc.hallazgo;
  }

  /**
   * Manda el parche y **revierte al valor anterior completo** si la API lo
   * rechaza.
   *
   * Se guarda `anterior` entero y no solo los campos tocados: son escrituras
   * optimistas, asi que entre el envio y el fallo la pantalla ya muestra el
   * valor nuevo. Reponer campo por campo dejaria la fila a medio camino si dos
   * ediciones se solapan.
   */
  function guardar(
    ncId: string,
    parche: Record<string, unknown>,
    anterior: NonConformity,
    queFallo: string,
  ) {
    if (!user?.tenantId) return;
    api
      .patch(`/audits/nonconformities/${ncId}`, parche, { tenantId: user.tenantId })
      .catch((error) => {
        setNonConformities((prev) => prev.map((nc) => (nc.id === ncId ? anterior : nc)));
        mostrarToast({ tipo: 'error', mensaje: queFallo, descripcion: mensajeDeError(error) });
      });
  }

  /**
   * Registra un hallazgo **y espera a la base** antes de darlo por hecho.
   *
   * Hasta el 13-sep era optimista y no funcionaba en ningún caso real: el
   * formulario pedía origen, datos del producto y del reclamo y **no se
   * mandaba ninguno** —salida no conforme y reclamo respondían 422 siempre—,
   * el responsable salía de `mockUsers` y la pantalla navegaba a
   * `nc-<timestamp>`, un id que la base nunca tuvo. Ahora devuelve el
   * registro que la API creó, con su id y sus etapas sembradas, o rechaza.
   */
  async function addNonConformity(input: {
    tenantId: string;
    plantId: string;
    hallazgo: string;
    /** Código de la escala de la empresa (`minor`, `major`, `critical`). */
    severidad: string;
    responsableId: string;
    tipoRegistro?: TipoRegistroMejora;
    origen?: string;
    auditItemId?: string;
    productData?: Record<string, string>;
    complaintData?: Record<string, string>;
  }): Promise<NonConformity> {
    const borrador: NonConformity = {
      id: 'nuevo',
      tenantId: input.tenantId,
      plantId: input.plantId,
      hallazgo: input.hallazgo,
      criticidad: CRITICIDAD_POR_SEVERITY[input.severidad] ?? 'media',
      estado: 'abierta',
      fechaDeteccion: new Date().toISOString(),
      responsableId: input.responsableId,
      cincoPorques: [],
      tipoRegistro: input.tipoRegistro,
    };

    const creada = await api.post<Record<string, unknown>>(
      '/audits/nonconformities/',
      {
        // `code` lleva la marca de tiempo: hay un UNIQUE (tenant, code) y dos
        // hallazgos del mismo día tienen que poder convivir.
        code: `NC-${new Date().toISOString().slice(0, 10)}-${Date.now() % 100000}`,
        title: etiqueta(borrador),
        description: input.hallazgo,
        severity: input.severidad,
        ...(input.plantId ? { facility_id: input.plantId } : {}),
        ...(input.responsableId ? { owner_user_id: input.responsableId } : {}),
        ...(input.tipoRegistro ? { record_type: input.tipoRegistro } : {}),
        ...(input.origen ? { detection_origin: input.origen } : {}),
        ...(input.auditItemId ? { audit_item_id: input.auditItemId } : {}),
        ...(input.productData ? { product_data: input.productData } : {}),
        ...(input.complaintData ? { complaint_data: input.complaintData } : {}),
      },
      { tenantId: input.tenantId },
    );
    const nc = mapApiNonConformity(creada);
    if (!nc) throw new Error('La API respondió sin un registro reconocible.');
    setNonConformities((prev) => [...prev, nc]);

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: nc.id,
      entidadLabel: etiqueta(nc),
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: 'Registró el hallazgo',
      cambios: [
        { campo: 'Criticidad', antes: null, despues: CRITICIDAD_LABEL[nc.criticidad] },
        { campo: 'Estado', antes: null, despues: NC_ESTADO_LABEL.abierta },
      ],
      motivo: input.hallazgo,
    });

    return nc;
  }

  function updatePorques(ncId: string, cincoPorques: string[]) {
    const anterior = nonConformities.find((nc) => nc.id === ncId);
    if (!anterior) return;

    const nuevoEstado = anterior.estado === 'abierta' ? 'en_tratamiento' : anterior.estado;

    setNonConformities((prev) =>
      prev.map((nc) => (nc.id !== ncId ? nc : { ...nc, cincoPorques, estado: nuevoEstado })),
    );

    const causaRaiz = cincoPorques.filter(Boolean).at(-1) ?? null;

    guardar(
      ncId,
      {
        root_cause_answers: cincoPorques,
        ...(nuevoEstado !== anterior.estado ? { status: STATUS_EN_TRATAMIENTO } : {}),
      },
      anterior,
      'No se pudo guardar el análisis de causa raíz',
    );

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: ncId,
      entidadLabel: etiqueta(anterior),
      tenantId: anterior.tenantId,
      accion: 'actualizado',
      resumen: 'Actualizó el análisis de causa raíz (5 ¿Por qué?)',
      cambios: [
        {
          campo: 'Porqués completados',
          antes: String(anterior.cincoPorques.filter(Boolean).length),
          despues: String(cincoPorques.filter(Boolean).length),
        },
        ...(nuevoEstado !== anterior.estado
          ? [{ campo: 'Estado', antes: NC_ESTADO_LABEL[anterior.estado], despues: NC_ESTADO_LABEL[nuevoEstado] }]
          : []),
      ],
      ...(causaRaiz ? { motivo: `Causa raíz identificada: ${causaRaiz}` } : {}),
    });
  }

  // `updateEtapas` se quitó el 13-sep: escribía el JSONB provisorio
  // `improvement_stages`, que el cierre no mira. Las etapas viven en
  // `improvement_stage_entries` y las lee y escribe `lib/etapas-mejora.ts`.


  function closeNonConformity(ncId: string, responsableId: string) {
    const anterior = nonConformities.find((nc) => nc.id === ncId);
    if (!anterior || anterior.estado === 'cerrada') return;

    setNonConformities((prev) =>
      prev.map((nc) =>
        nc.id !== ncId
          ? nc
          : { ...nc, estado: 'cerrada', cierre: { fecha: new Date().toISOString(), responsableId, firmada: true } },
      ),
    );

    // Va por `/close` y no por un PATCH: la base exige
    // `(status='closed') = (closed_at IS NOT NULL)`, asi que mandar solo el
    // estado viola el CHECK y la fila nunca se cerraba. El endpoint ademas
    // rechaza el cierre si quedan planes de accion abiertos, que es la regla
    // de negocio que un PATCH suelto se saltaba.
    if (user?.tenantId) {
      api
        .post(`/audits/nonconformities/${ncId}/close`, {}, { tenantId: user.tenantId })
        .catch((error) => {
          setNonConformities((prev) => prev.map((nc) => (nc.id === ncId ? anterior : nc)));
          mostrarToast({
            tipo: 'error',
            mensaje: 'No se pudo cerrar la no conformidad',
            descripcion: mensajeDeError(error),
          });
        });
    }

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: ncId,
      entidadLabel: etiqueta(anterior),
      tenantId: anterior.tenantId,
      accion: 'cerrado',
      resumen: 'Cerró la no conformidad con firma',
      cambios: [
        { campo: 'Estado', antes: NC_ESTADO_LABEL[anterior.estado], despues: NC_ESTADO_LABEL.cerrada },
        { campo: 'Firmada', antes: 'No', despues: 'Sí' },
      ],
      aprobadoPorId: responsableId,
      aprobadoPorNombre: users.find((u) => u.id === responsableId)?.nombre ?? responsableId,
    });
  }

  // **Mientras no se haya preguntado POR ESTA empresa, se sigue cargando.**
  // El efecto baja `loading` a `false` cuando todavia no hay sesion, y al
  // llegar el tenant no lo vuelve a subir: quedaba una ventana con la lista
  // vacia y `loading` en `false`, y las fichas afirmaban "No encontramos esto"
  // sobre algo que si existe, durante todo el viaje de red.
  const cargandoDeVerdad = loading || (!!user?.tenantId && datosDe !== user.tenantId);

  function agregarAuditoria(raw: Record<string, unknown>): Audit | null {
    const nueva = mapApiAudit(raw);
    if (nueva) setAudits((prev) => [...prev.filter((a) => a.id !== nueva.id), nueva]);
    return nueva;
  }

  function actualizarEstadoAuditoria(auditId: string, statusDeLaApi: string) {
    const estado = ESTADO_POR_STATUS[statusDeLaApi];
    if (!estado) return;
    setAudits((prev) => prev.map((a) => (a.id === auditId ? { ...a, estado } : a)));
  }

  return (
    <AuditsContext.Provider
      value={{
        audits,
        nonConformities,
        loading: cargandoDeVerdad,
        errorDeCarga,
        addNonConformity,
        updatePorques,
        closeNonConformity,
        agregarAuditoria,
        actualizarEstadoAuditoria,
      }}
    >
      {children}
    </AuditsContext.Provider>
  );
}

export function useAudits() {
  const ctx = useContext(AuditsContext);
  if (!ctx) throw new Error('useAudits debe usarse dentro de <AuditsProvider>');
  return ctx;
}
