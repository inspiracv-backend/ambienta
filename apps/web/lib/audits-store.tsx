'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Audit, NonConformity, EtapasMejora, TipoRegistroMejora } from '@ambienta/shared';
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
  addNonConformity: (input: {
    tenantId: string;
    plantId: string;
    auditId?: string;
    hallazgo: string;
    criticidad: NonConformity['criticidad'];
    responsableId: string;
    tipoRegistro?: TipoRegistroMejora;
  }) => NonConformity;
  updatePorques: (ncId: string, cincoPorques: string[]) => void;
  updateEtapas: (ncId: string, etapas: EtapasMejora) => void;
  closeNonConformity: (ncId: string, responsableId: string) => void;
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
  cancelled: 'cerrada',
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
      ...(raw.improvement_stages && typeof raw.improvement_stages === 'object'
        && !Array.isArray(raw.improvement_stages)
        && Object.keys(raw.improvement_stages).length > 0
        ? { etapasMejora: raw.improvement_stages as EtapasMejora }
        : {}),
      ...(raw.record_type ? { tipoRegistro: String(raw.record_type) as TipoRegistroMejora } : {}),
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
      fecha: raw.planned_start ? String(raw.planned_start) : new Date().toISOString(),
      estado: ESTADO_POR_STATUS[String(raw.status ?? '')] ?? 'planificada',
      // La API los tiene como `scope` (texto libre) y en tablas aparte; el
      // listado no los trae. Se pueblan al abrir el detalle.
      procesos: [],
      normativaIds: [],
    };
  } catch {
    return null;
  }
}

export function AuditsProvider({ children }: { children: ReactNode }) {
  const [audits, setAudits] = useState<Audit[]>([]);
  const [nonConformities, setNonConformities] = useState<NonConformity[]>([]);
  const [loading, setLoading] = useState(true);
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
      .finally(() => { if (!cancelled) setLoading(false); });
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

  function addNonConformity(input: {
    tenantId: string;
    plantId: string;
    auditId?: string;
    hallazgo: string;
    criticidad: NonConformity['criticidad'];
    responsableId: string;
    tipoRegistro?: TipoRegistroMejora;
  }): NonConformity {
    const nc: NonConformity = {
      id: `nc-${Date.now()}`,
      tenantId: input.tenantId,
      plantId: input.plantId,
      auditId: input.auditId,
      hallazgo: input.hallazgo,
      criticidad: input.criticidad,
      estado: 'abierta',
      fechaDeteccion: new Date().toISOString(),
      responsableId: input.responsableId,
      cincoPorques: [],
      tipoRegistro: input.tipoRegistro,
    };
    setNonConformities((prev) => [...prev, nc]);

    // `code` y `title` son NOT NULL y no se mandaban: la fila no entraba.
    // El codigo lleva la marca de tiempo porque hay un UNIQUE (tenant, code) y
    // dos hallazgos del mismo dia tienen que poder convivir.
    api
      .post<Record<string, unknown>>(
        '/audits/nonconformities/',
        {
          code: `NC-${new Date().toISOString().slice(0, 10)}-${Date.now() % 100000}`,
          title: etiqueta(nc),
          description: input.hallazgo,
          severity: SEVERITY_POR_CRITICIDAD[input.criticidad],
          ...(input.plantId ? { facility_id: input.plantId } : {}),
          ...(input.responsableId ? { owner_user_id: input.responsableId } : {}),
          ...(input.tipoRegistro ? { record_type: input.tipoRegistro } : {}),
        },
        { tenantId: input.tenantId },
      )
      .then((creada) => {
        // El id local era `nc-<timestamp>`, que la API no conoce: sin este
        // reemplazo toda escritura posterior sobre este hallazgo apuntaria a
        // una fila inexistente y volveria a fallar en silencio.
        const real = mapApiNonConformity(creada);
        if (real) setNonConformities((prev) => prev.map((x) => (x.id === nc.id ? real : x)));
      })
      .catch((error) => {
        // Revertir: mostrar un hallazgo que la base no tiene es peor que no
        // mostrarlo, porque nadie vuelve a registrarlo.
        setNonConformities((prev) => prev.filter((x) => x.id !== nc.id));
        mostrarToast({
          tipo: 'error',
          mensaje: 'No se pudo registrar el hallazgo',
          descripcion: mensajeDeError(error),
        });
      });

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: nc.id,
      entidadLabel: etiqueta(nc),
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: 'Registró el hallazgo',
      cambios: [
        { campo: 'Criticidad', antes: null, despues: CRITICIDAD_LABEL[input.criticidad] },
        { campo: 'Estado', antes: null, despues: NC_ESTADO_LABEL.abierta },
        ...(input.auditId ? [{ campo: 'Auditoría de origen', antes: null, despues: input.auditId }] : []),
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

  function updateEtapas(ncId: string, etapas: EtapasMejora) {
    const anterior = nonConformities.find((nc) => nc.id === ncId);
    if (!anterior) return;

    const nuevoEstado = anterior.estado === 'abierta' ? 'en_tratamiento' : anterior.estado;

    setNonConformities((prev) =>
      prev.map((nc) =>
        nc.id !== ncId ? nc : { ...nc, etapasMejora: etapas, estado: nuevoEstado },
      ),
    );

    guardar(
      ncId,
      {
        improvement_stages: etapas,
        ...(nuevoEstado !== anterior.estado ? { status: STATUS_EN_TRATAMIENTO } : {}),
      },
      anterior,
      'No se pudieron guardar las etapas del tratamiento',
    );

    registrar({
      entidadTipo: 'no_conformidad',
      entidadId: ncId,
      entidadLabel: etiqueta(anterior),
      tenantId: anterior.tenantId,
      accion: 'actualizado',
      resumen: 'Actualizó las etapas del tratamiento',
      cambios: [
        ...(nuevoEstado !== anterior.estado
          ? [{ campo: 'Estado', antes: NC_ESTADO_LABEL[anterior.estado], despues: NC_ESTADO_LABEL[nuevoEstado] }]
          : []),
      ],
    });
  }

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

  return (
    <AuditsContext.Provider value={{ audits, nonConformities, loading, errorDeCarga, addNonConformity, updatePorques, updateEtapas, closeNonConformity }}>
      {children}
    </AuditsContext.Provider>
  );
}

export function useAudits() {
  const ctx = useContext(AuditsContext);
  if (!ctx) throw new Error('useAudits debe usarse dentro de <AuditsProvider>');
  return ctx;
}
