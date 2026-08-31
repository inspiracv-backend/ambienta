'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Obligation, ObligationStatus, ObligationTask, SistemaDeclaracion } from '@ambienta/shared';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api, mensajeDeError } from '@/lib/api-client';

const ESTADO_OBLIGACION_LABEL: Record<ObligationStatus, string> = {
  vigente: 'Vigente',
  por_vencer: 'Por vencer',
  vencida: 'Vencida',
  sin_evidencia: 'Sin evidencia',
};

interface ObligationsContextValue {
  obligations: Obligation[];
  loading: boolean;
  /**
   * Por que la lista esta vacia, si es que fallo (#208).
   *
   * `null` = se pregunto y esto es lo que hay. Un texto = **no se pudo
   * preguntar**, y la pantalla tiene que decirlo: sin esto un fallo de red se
   * ve igual que "esta empresa no tiene ninguno".
   */
  errorDeCarga: string | null;
  updateTask: (obligationId: string, taskId: string, updates: Partial<ObligationTask>) => void;
  addTask: (obligationId: string, input: { titulo: string; vencimiento: string; responsableId: string }) => void;
  /**
   * Mueve la declaracion por su flujo (RF-31, #115).
   *
   * Un solo metodo con la accion por parametro y no tres: las tres hacen lo
   * mismo —un POST, releer, y mostrar el error del servidor— y separarlas
   * invitaba a que una se olvidara de recargar.
   *
   * **No es optimista.** Las transiciones las valida el servidor y puede
   * rechazarlas con 409 (aprobar sin folio, saltarse un paso). Pintar el
   * estado nuevo antes de saberlo mostraria "aceptada" sobre algo que la API
   * acaba de rechazar.
   */
  moverDeclaracion: (
    obligationId: string,
    accion: 'submit' | 'approve' | 'reject' | 'fulfill',
    datos?: { folio?: string; motivo?: string },
  ) => Promise<void>;
  addObligation: (input: {
    nombre: string;
    sistema: SistemaDeclaracion;
    periodo: string;
    tenantId: string;
    plantId: string;
    responsableId: string;
    proximoVencimiento: string;
  }) => void;
}

const ObligationsContext = createContext<ObligationsContextValue | null>(null);

/**
 * Traduce el estado de la API al de la pantalla.
 *
 * El mapa anterior traducía cuatro valores y **dos no existían**: `upcoming` y
 * `fulfilled` no están en el CHECK de `obligations.status`, que admite `draft`,
 * `open`, `in_progress`, `submitted`, `accepted`, `rejected`, `overdue` y
 * `closed`. Como el mapa caía a 'vigente' por defecto, seis de los ocho
 * estados reales se mostraban como vigentes — incluida una obligación
 * rechazada.
 *
 * `por_vencer` no viene de la API porque no es un estado, es una cuenta de
 * días: se deriva de la fecha, con el mismo umbral que usa el tablero.
 */
/**
 * Traduce la urgencia que calcula el servidor al semáforo de la pantalla.
 *
 * **El navegador ya no la calcula.** Tenía su propia cuenta con
 * `DIAS_PARA_AVISAR = 30` mientras el servidor usa 15 (`DIAS_PROXIMO` en
 * `services/declaracion.py`): dos criterios escritos dos veces, **ya
 * separados**, y una obligación a 20 días salía "por vencer" en pantalla y
 * "vigente" en cualquier otra lectura de la API. Es la misma trampa que el
 * porcentaje de cumplimiento entre la pantalla y el informe.
 *
 * `sin_plazo` cae en `vigente` **y eso pierde información**: una obligación sin
 * fecha no va bien, es que nadie le puso plazo. `ObligationStatus` tiene cuatro
 * valores y ninguno dice eso; agregarlo toca `StatusBadge` y las seis pantallas
 * que lo usan, así que queda anotado en vez de resuelto a medias.
 */
const SEMAFORO: Record<string, ObligationStatus> = {
  vencida: 'vencida',
  critica: 'por_vencer',
  proxima: 'por_vencer',
  resuelta: 'vigente',
  vigente: 'vigente',
  sin_plazo: 'vigente',
};

function mapEstado(
  status: string,
  vencimiento: string,
  urgencia?: string,
): ObligationStatus {
  // Sin enviar todavía, o rechazada y hay que rehacerla. Va **antes** que la
  // urgencia: es una afirmación sobre lo que falta hacer, no sobre el plazo.
  if (status === 'draft' || status === 'rejected') return 'sin_evidencia';

  if (urgencia && urgencia in SEMAFORO) return SEMAFORO[urgencia]!;

  // Respaldo para los datos de ejemplo, que no pasan por la API. Deliberadamente
  // tosco: no reimplementa los tramos del servidor, solo distingue lo vencido.
  if (status === 'overdue') return 'vencida';
  return new Date(vencimiento).getTime() < Date.now() ? 'vencida' : 'vigente';
}

/**
 * El sistema de declaración sale del código, que lo lleva embebido
 * (`OBL-SIDREP-2026S1`). No hay columna propia en la base: el catálogo lo
 * modela como plantilla, y la obligación solo guarda su código.
 */
function mapSistema(code: string): SistemaDeclaracion {
  const conocidos: SistemaDeclaracion[] = ['RETC', 'SINADER', 'SIDREP', 'DAE'];
  const encontrado = conocidos.find((s) => code.toUpperCase().includes(s));
  if (encontrado) return encontrado;
  return code.toUpperCase().includes('REP') ? 'Ley REP' : 'RETC';
}

function mapPeriodo(inicio: unknown, fin: unknown): string {
  if (!inicio || !fin) return '';
  const anio = String(inicio).slice(0, 4);
  const mesInicio = Number(String(inicio).slice(5, 7));
  const mesFin = Number(String(fin).slice(5, 7));
  if (mesInicio === 1 && mesFin === 12) return anio;
  return `${anio} · ${mesInicio <= 6 ? '1er' : '2do'} semestre`;
}

/**
 * La URL del portal de cada obligacion, resuelta contra el catalogo.
 *
 * La API devuelve `retc_system_id`; la direccion vive en `retc_systems`. Se
 * cruza aca, en **una sola peticion para todas** las obligaciones, y no
 * pidiendo el sistema de cada una: con veinte declaraciones eso serian veinte
 * viajes para pintar veinte enlaces.
 *
 * Si el catalogo no responde, las obligaciones llegan igual y el boton "ir al
 * sistema oficial" simplemente no aparece. Perder un atajo no justifica dejar
 * la pantalla vacia.
 */
async function conUrlDelSistema(
  filas: Record<string, unknown>[],
  tenantId: string,
): Promise<Record<string, unknown>[]> {
  if (!filas.some((f) => f.retc_system_id)) return filas;

  const sistemas = await api
    .get<Record<string, unknown>[]>('/catalog/retc-systems', { tenantId })
    .catch(() => []);
  const urlPorId = new Map(
    sistemas.map((sys) => [String(sys.id), String(sys.url_oficial ?? "")] as [string, string]),
  );

  return filas.map((f) =>
    f.retc_system_id
      ? { ...f, __sistema_url: urlPorId.get(String(f.retc_system_id)) ?? '' }
      : f,
  );
}

function mapApiObligation(raw: Record<string, unknown>): Obligation | null {
  try {
    // `due_at` y `owner_user_id`, no `due_date` ni `assigned_user_id`: esos dos
    // nombres no existen en la API y por eso toda obligación mostraba la fecha
    // de hoy como vencimiento y ningún responsable.
    const vencimiento = raw.due_at
      ? String(raw.due_at)
      : new Date().toISOString();
    const code = String(raw.code ?? '');
    const datos = (raw.data ?? {}) as Record<string, unknown>;
    const motivoRechazo = datos.motivo_rechazo ? String(datos.motivo_rechazo) : '';
    // La URL la resuelve el llamador contra el catalogo de sistemas: el mapeo
    // de una fila no puede salir a la red.
    const urlDelSistema = raw.__sistema_url ? String(raw.__sistema_url) : '';

    return {
      id: String(raw.id),
      tenantId: String(raw.tenant_id ?? ''),
      plantId: String(raw.facility_id ?? ''),
      sistema: mapSistema(code),
      nombre: String(raw.title ?? code),
      periodo: mapPeriodo(raw.period_start, raw.period_end),
      estado: mapEstado(
        String(raw.status ?? 'draft'),
        vencimiento,
        raw.urgencia ? String(raw.urgencia) : undefined,
      ),
      proximoVencimiento: vencimiento,
      responsableId: raw.owner_user_id ? String(raw.owner_user_id) : '',
      tasks: [],
      // El vinculo con la Matriz Legal (RF-09, RF-14). Se mapea aunque hoy solo
      // lo lea el detalle: sin esto, la obligacion generada desde un articulo
      // llega al navegador **sin rastro de donde vino**, y la relacion
      // bidireccional existiria en la base sin verse en ningun lado.
      ...(raw.article_compliance_id
        ? { articuloOrigenId: String(raw.article_compliance_id) }
        : {}),
      ...(raw.matrix_norm_id ? { normaOrigenId: String(raw.matrix_norm_id) } : {}),
      ...(raw.external_receipt ? { folio: String(raw.external_receipt) } : {}),
      ...(motivoRechazo ? { motivoRechazo } : {}),
      ...(urlDelSistema ? { sistemaUrl: urlDelSistema } : {}),
    };
  } catch {
    return null;
  }
}

export function ObligationsProvider({ children }: { children: ReactNode }) {
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    const tenantId = user.tenantId;
    api
      .get<Record<string, unknown>[]>('/obligations/', { tenantId })
      .then((data) => conUrlDelSistema(data, tenantId))
      .then((data) => {
        if (cancelled) return;
        const mapped = data.map(mapApiObligation).filter((o): o is Obligation => o !== null);
        // **Se escribe siempre, incluso vacio** (#208). El `if (length > 0)`
        // de antes no distinguia dos cosas muy distintas: que la API fallara
        // —donde quedarse con lo que hay es un respaldo razonable— y que
        // respondiera **cero filas**, donde quedarse con los datos de ejemplo
        // es mostrar algo que no existe.
        //
        // El `catch` sigue conservando lo ultimo conocido, asi que trabajar sin
        // backend levantado sigue funcionando: ahi la peticion falla, no
        // devuelve vacio.
        setObligations(mapped);
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

  function recomputeEstado(tasks: ObligationTask[]): ObligationStatus {
    if (tasks.some((t) => t.estado === 'vencida')) return 'vencida';
    if (tasks.some((t) => t.estado === 'sin_evidencia')) return 'sin_evidencia';
    if (tasks.some((t) => t.estado === 'por_vencer')) return 'por_vencer';
    return 'vigente';
  }

  function updateTask(obligationId: string, taskId: string, updates: Partial<ObligationTask>) {
    const obligacion = obligations.find((ob) => ob.id === obligationId);
    const tareaAnterior = obligacion?.tasks.find((t) => t.id === taskId);

    setObligations((prev) =>
      prev.map((ob) => {
        if (ob.id !== obligationId) return ob;
        const tasks = ob.tasks.map((t) => (t.id === taskId ? { ...t, ...updates } : t));
        return { ...ob, tasks, estado: recomputeEstado(tasks) };
      }),
    );

    if (user?.tenantId) {
      api.patch(`/obligations/tasks/${taskId}`, updates, { tenantId: user.tenantId }).catch(() => {});
    }

    if (!obligacion || !tareaAnterior) return;

    const cambios = [];
    if (updates.estado !== undefined && updates.estado !== tareaAnterior.estado) {
      cambios.push({
        campo: 'Estado',
        antes: ESTADO_OBLIGACION_LABEL[tareaAnterior.estado],
        despues: ESTADO_OBLIGACION_LABEL[updates.estado],
      });
    }
    if (updates.evidenciaUrl !== undefined && updates.evidenciaUrl !== tareaAnterior.evidenciaUrl) {
      cambios.push({ campo: 'Evidencia', antes: tareaAnterior.evidenciaUrl ?? null, despues: updates.evidenciaUrl ?? null });
    }
    if (updates.responsableId !== undefined && updates.responsableId !== tareaAnterior.responsableId) {
      cambios.push({ campo: 'Responsable', antes: tareaAnterior.responsableId, despues: updates.responsableId });
    }
    if (updates.vencimiento !== undefined && updates.vencimiento !== tareaAnterior.vencimiento) {
      cambios.push({ campo: 'Vencimiento', antes: tareaAnterior.vencimiento, despues: updates.vencimiento });
    }
    if (cambios.length === 0) return;

    registrar({
      entidadTipo: 'tarea',
      entidadId: taskId,
      entidadLabel: `${tareaAnterior.titulo} — ${obligacion.nombre}`,
      tenantId: obligacion.tenantId,
      accion: 'actualizado',
      resumen: 'Actualizó la tarea',
      cambios,
    });
  }

  function addTask(obligationId: string, input: { titulo: string; vencimiento: string; responsableId: string }) {
    const obligacion = obligations.find((ob) => ob.id === obligationId);
    const taskId = `task-${Date.now()}`;

    setObligations((prev) =>
      prev.map((ob) => {
        if (ob.id !== obligationId) return ob;
        const newTask: ObligationTask = {
          id: taskId,
          obligationId,
          titulo: input.titulo,
          vencimiento: input.vencimiento,
          responsableId: input.responsableId,
          estado: 'vigente',
        };
        const tasks = [...ob.tasks, newTask];
        return { ...ob, tasks, estado: recomputeEstado(tasks) };
      }),
    );

    if (user?.tenantId) {
      api.post(`/obligations/${obligationId}/tasks`, {
        title: input.titulo,
        due_date: input.vencimiento,
        assigned_user_id: input.responsableId,
        task_type: 'action',
      }, { tenantId: user.tenantId }).catch(() => {});
    }

    if (!obligacion) return;

    registrar({
      entidadTipo: 'tarea',
      entidadId: taskId,
      entidadLabel: `${input.titulo} — ${obligacion.nombre}`,
      tenantId: obligacion.tenantId,
      accion: 'creado',
      resumen: `Agregó la tarea a ${obligacion.nombre}`,
      cambios: [{ campo: 'Vencimiento', antes: null, despues: input.vencimiento }],
    });
  }

  async function moverDeclaracion(
    obligationId: string,
    accion: 'submit' | 'approve' | 'reject' | 'fulfill',
    datos: { folio?: string; motivo?: string } = {},
  ) {
    if (!user?.tenantId) throw new Error('Sin sesion no se puede mover una declaracion.');

    await api.post(`/obligations/${obligationId}/${accion}`, datos, {
      tenantId: user.tenantId,
    });

    // Se relee en vez de parchear en memoria: el servidor puede haber tocado
    // mas de lo que se le pidio —aprobar fija el folio, rechazar escribe el
    // motivo— y adivinar cual quedaria desincronizado a la primera.
    const filas = await conUrlDelSistema(
      await api.get<Record<string, unknown>[]>('/obligations/', { tenantId: user.tenantId }),
      user.tenantId,
    );
    const mapeadas = filas.map(mapApiObligation).filter(Boolean) as Obligation[];
    // Relectura tras mover una declaracion. Se escribe igual que en la
    // carga inicial: si la API dice que no hay ninguna, la pantalla tiene que
    // decir lo mismo. Un fallo de red no llega aca — `moverDeclaracion` deja
    // que la excepcion suba para que la pantalla muestre el error.
    setObligations(mapeadas);
  }

  function addObligation(input: {
    nombre: string;
    sistema: SistemaDeclaracion;
    periodo: string;
    tenantId: string;
    plantId: string;
    responsableId: string;
    proximoVencimiento: string;
  }) {
    const newObligation: Obligation = {
      id: `obl-${Date.now()}`,
      tenantId: input.tenantId,
      plantId: input.plantId,
      sistema: input.sistema,
      nombre: input.nombre,
      periodo: input.periodo,
      estado: 'vigente',
      proximoVencimiento: input.proximoVencimiento,
      responsableId: input.responsableId,
      tasks: [],
    };
    setObligations((prev) => [...prev, newObligation]);

    api.post('/obligations/', {
      title: input.nombre,
      facility_id: input.plantId,
      assigned_user_id: input.responsableId,
      due_date: input.proximoVencimiento,
      status: 'open',
    }, { tenantId: input.tenantId }).catch(() => {});

    registrar({
      entidadTipo: 'obligacion',
      entidadId: newObligation.id,
      entidadLabel: newObligation.nombre,
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: `Creó la obligación (${input.sistema})`,
      cambios: [
        { campo: 'Sistema', antes: null, despues: input.sistema },
        { campo: 'Período', antes: null, despues: input.periodo },
        { campo: 'Próximo vencimiento', antes: null, despues: input.proximoVencimiento },
      ],
    });
  }

  return (
    <ObligationsContext.Provider value={{ obligations, loading, errorDeCarga, updateTask, addTask, addObligation, moverDeclaracion }}>
      {children}
    </ObligationsContext.Provider>
  );
}

export function useObligations() {
  const ctx = useContext(ObligationsContext);
  if (!ctx) throw new Error('useObligations debe usarse dentro de <ObligationsProvider>');
  return ctx;
}
