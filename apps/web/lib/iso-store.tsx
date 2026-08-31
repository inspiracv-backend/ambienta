'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';

/**
 * Aspectos ambientales, riesgos/oportunidades y equipos regulados (ISO 14001).
 *
 * ## Por qué existía este archivo y no existía
 *
 * Las tres pantallas leían `mocks/` **directamente**, sin tocar la API. No es
 * que estuvieran a medias: no había ni una llamada. Filtrabas, y filtrabas
 * datos de ejemplo; no había forma de crear, editar ni borrar nada. La API, en
 * cambio, tenía CRUD completo de las tres desde hacía tiempo.
 *
 * ## Por qué un store para las tres y no tres stores
 *
 * Porque la cadena de 14001 es una sola: **un aspecto significativo se trata
 * con un riesgo/oportunidad, que se trata con un plan de acción**. La pregunta
 * que importa en una auditoría —"¿qué aspecto significativo quedó sin
 * tratar?"— no se puede contestar mirando sólo los aspectos: hay que saber si
 * algún riesgo lo referencia. Con tres stores aislados, cada pantalla tendría
 * que pedir las otras dos.
 *
 * Son colecciones chicas —decenas de filas por empresa— así que traerlas
 * juntas cuesta tres peticiones y evita el problema entero.
 *
 * ## El modelo de la API manda
 *
 * `packages/shared` define estas entidades con más campos de los que la base
 * guarda: `etapaCicloVida`, el impacto como texto, la lista de riesgos
 * vinculados. **Se ignoran a propósito.** Mostrar un campo que no se persiste
 * es la forma más silenciosa de perder un dato: la persona lo escribe, ve
 * "guardado", recarga y no está. Ya pasó en este repositorio con
 * `evidence_url`.
 */

export interface AspectoApi {
  id: string;
  facilityId: string;
  procesoId: string | null;
  /** El requisito legal con el que se trata. `null` = eslabón sin cerrar. */
  articleComplianceId: string | null;
  actividad: string;
  aspecto: string;
  tipoImpacto: string;
  condicionOperacion: string;
  puntajeSeveridad: number | null;
  puntajeFrecuencia: number | null;
  puntajeLegal: number | null;
  puntajeTotal: number | null;
  /** `significant` | `not_significant` | `pending`. */
  significancia: string;
  responsableId: string | null;
}

export interface RiesgoApi {
  id: string;
  facilityId: string | null;
  aspectoAmbientalId: string | null;
  planAccionId: string | null;
  codigo: string;
  /** `risk` | `opportunity`. */
  tipo: string;
  descripcion: string;
  origen: string;
  nivel: string;
  tratamiento: string | null;
  estado: string;
  responsableId: string | null;
  fechaRevision: string | null;
}

/** Una planta, con su **id real**. Ver `plantas` en el store. */
export interface PlantaApi {
  id: string;
  nombre: string;
}

export interface EquipoApi {
  id: string;
  facilityId: string;
  nombre: string;
  tipo: string;
  marca: string | null;
  modelo: string | null;
  autoridad: string | null;
  numeroInscripcion: string | null;
  inscripcionVence: string | null;
  estado: string;
}

function mapAspecto(r: Record<string, unknown>): AspectoApi {
  return {
    id: String(r.id),
    facilityId: String(r.facility_id ?? ''),
    procesoId: r.process_id ? String(r.process_id) : null,
    articleComplianceId: r.article_compliance_id ? String(r.article_compliance_id) : null,
    actividad: String(r.activity ?? ''),
    aspecto: String(r.aspect ?? ''),
    tipoImpacto: String(r.impact_type ?? ''),
    condicionOperacion: String(r.operating_condition ?? 'normal'),
    puntajeSeveridad: r.severity_score == null ? null : Number(r.severity_score),
    puntajeFrecuencia: r.frequency_score == null ? null : Number(r.frequency_score),
    puntajeLegal: r.legal_score == null ? null : Number(r.legal_score),
    puntajeTotal: r.total_score == null ? null : Number(r.total_score),
    significancia: String(r.significance ?? 'pending'),
    responsableId: r.responsible_user_id ? String(r.responsible_user_id) : null,
  };
}

function mapRiesgo(r: Record<string, unknown>): RiesgoApi {
  return {
    id: String(r.id),
    facilityId: r.facility_id ? String(r.facility_id) : null,
    aspectoAmbientalId: r.environmental_aspect_id ? String(r.environmental_aspect_id) : null,
    planAccionId: r.action_plan_id ? String(r.action_plan_id) : null,
    codigo: String(r.code ?? ''),
    tipo: String(r.entry_type ?? 'risk'),
    descripcion: String(r.description ?? ''),
    origen: String(r.origin ?? ''),
    nivel: String(r.risk_level ?? 'medium'),
    tratamiento: r.treatment ? String(r.treatment) : null,
    estado: String(r.status ?? 'identified'),
    responsableId: r.owner_user_id ? String(r.owner_user_id) : null,
    fechaRevision: r.review_date ? String(r.review_date) : null,
  };
}

function mapEquipo(r: Record<string, unknown>): EquipoApi {
  return {
    id: String(r.id),
    facilityId: String(r.facility_id ?? ''),
    nombre: String(r.name ?? ''),
    tipo: String(r.equipment_type ?? ''),
    marca: r.brand ? String(r.brand) : null,
    modelo: r.model ? String(r.model) : null,
    autoridad: r.registration_authority ? String(r.registration_authority) : null,
    numeroInscripcion: r.registration_number ? String(r.registration_number) : null,
    inscripcionVence: r.registration_expires_at ? String(r.registration_expires_at) : null,
    estado: String(r.status ?? 'active'),
  };
}

/**
 * Un aspecto significativo **sin nada que lo trate**.
 *
 * Es el hallazgo más común en una auditoría de 14001: la empresa identificó el
 * problema y no hizo nada. Se necesita la lista de riesgos para responderlo, y
 * por eso las tres colecciones viven en el mismo store.
 */
export function aspectoSinTratar(aspecto: AspectoApi, riesgos: RiesgoApi[]): boolean {
  if (aspecto.significancia !== 'significant') return false;
  if (aspecto.articleComplianceId) return false;
  return !riesgos.some((r) => r.aspectoAmbientalId === aspecto.id);
}

interface IsoContextValue {
  aspectos: AspectoApi[];
  /**
   * Las plantas, pedidas **acá y no al store de empresas**.
   *
   * `useTenants()` pide `/tenants/` sin declarar empresa, y esa ruta responde
   * 401 cuando la sesión viaja por `X-Tenant-Id` —el modo sin Clerk—. Como el
   * `Promise.all` entero se cae, el store se queda con `mockTenants`, cuyas
   * plantas tienen identificadores de ejemplo (`planta-rancagua`) mientras la
   * API usa UUID.
   *
   * Se detectó creando un equipo desde la pantalla: la API respondió **422,
   * `facility_id` no es un UUID válido**. Y el filtro por planta tampoco podía
   * funcionar — comparaba un slug contra un UUID, así que elegir una planta
   * dejaba la tabla vacía sin explicación.
   */
  plantas: PlantaApi[];
  riesgos: RiesgoApi[];
  equipos: EquipoApi[];
  cargando: boolean;
  error: string | null;
  /**
   * Que listados vinieron **cortados** por el tope del servidor (#167).
   *
   * Vacío = se ve todo. Se expone en vez de esconderlo porque una lista
   * cortada se ve igual que una completa, y en una matriz de aspectos eso
   * significa creer que se revisó todo cuando falta un pedazo.
   */
  truncado: string[];
  recargar: () => void;

  crearAspecto: (datos: Record<string, unknown>) => Promise<boolean>;
  editarAspecto: (id: string, datos: Record<string, unknown>) => Promise<boolean>;
  borrarAspecto: (id: string) => Promise<boolean>;

  crearRiesgo: (datos: Record<string, unknown>) => Promise<boolean>;
  editarRiesgo: (id: string, datos: Record<string, unknown>) => Promise<boolean>;
  borrarRiesgo: (id: string) => Promise<boolean>;

  crearEquipo: (datos: Record<string, unknown>) => Promise<boolean>;
  editarEquipo: (id: string, datos: Record<string, unknown>) => Promise<boolean>;
  borrarEquipo: (id: string) => Promise<boolean>;
}

const IsoContext = createContext<IsoContextValue | null>(null);

export function IsoProvider({ children }: { children: ReactNode }) {
  const { user, cargando: cargandoSesion } = useSession();
  const { mostrarToast } = useToast();
  const tenantId = user?.tenantId ?? null;

  const [aspectos, setAspectos] = useState<AspectoApi[]>([]);
  const [plantas, setPlantas] = useState<PlantaApi[]>([]);
  const [riesgos, setRiesgos] = useState<RiesgoApi[]>([]);
  const [equipos, setEquipos] = useState<EquipoApi[]>([]);
  const [cargando, setCargando] = useState(true);
  const [truncado, setTruncado] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reintento, setReintento] = useState(0);

  useEffect(() => {
    if (!tenantId) {
      if (!cargandoSesion) setCargando(false);
      return;
    }
    let vigente = true;
    setCargando(true);
    setError(null);

    const opts = { tenantId };
    // `getPagina` en vez de `get` para conservar `X-Has-More` (#167). La API
    // acota cada listado; sin leer esa cabecera, una empresa con 640 aspectos
    // veria 500 y **nada se lo diría** — el caso que #167 llama "más engañoso
    // que no paginar", porque una lista cortada se ve perfectamente normal.
    Promise.all([
      api.getPagina<Record<string, unknown>>('/iso14001/aspects?limit=500', opts),
      api.getPagina<Record<string, unknown>>('/iso14001/risks?limit=500', opts),
      api.getPagina<Record<string, unknown>>('/iso14001/equipment?limit=500', opts),
      api.get<Record<string, unknown>[]>('/facilities/', opts),
    ])
      .then(([pa, pr, pe, p]) => {
        if (!vigente) return;
        const a = pa.datos;
        const r = pr.datos;
        const e = pe.datos;
        setTruncado(
          [
            pa.hayMas && 'aspectos ambientales',
            pr.hayMas && 'riesgos y oportunidades',
            pe.hayMas && 'equipos regulados',
          ].filter(Boolean) as string[],
        );
        // **Se escribe siempre, incluso vacío.** Cero aspectos se ve como cero
        // aspectos: mostrar los de ejemplo haría creer que la empresa ya
        // levantó su matriz de aspectos cuando no la levantó, y eso es
        // justamente lo que una auditoría de 14001 va a pedir.
        setAspectos(Array.isArray(a) ? a.map(mapAspecto) : []);
        setRiesgos(Array.isArray(r) ? r.map(mapRiesgo) : []);
        setEquipos(Array.isArray(e) ? e.map(mapEquipo) : []);
        setPlantas(
          Array.isArray(p)
            ? p.map((x) => ({ id: String(x.id), nombre: String(x.name ?? x.code ?? '') }))
            : [],
        );
      })
      .catch((e: unknown) => {
        if (vigente) setError(mensajeDeError(e));
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });

    return () => {
      vigente = false;
    };
  }, [tenantId, cargandoSesion, reintento]);

  const recargar = useCallback(() => setReintento((n) => n + 1), []);

  /**
   * Escribe y **recarga desde la API** en vez de parchear en memoria.
   *
   * Varios campos los decide el servidor —`total_score` se calcula,
   * `significance` se deriva del umbral de la empresa— así que parchear con lo
   * que se mandó dejaría en pantalla números que la base no tiene. Ya pasó en
   * este repositorio: guardar sin releer da un "guardado" que se deshace al
   * recargar.
   */
  const escribir = useCallback(
    async (
      accion: () => Promise<unknown>,
      mensaje: string,
    ): Promise<boolean> => {
      if (!tenantId) return false;
      try {
        await accion();
        setReintento((n) => n + 1);
        mostrarToast({ tipo: 'exito', mensaje });
        return true;
      } catch (e: unknown) {
        mostrarToast({ tipo: 'error', mensaje: mensajeDeError(e) });
        return false;
      }
    },
    [tenantId, mostrarToast],
  );

  const opts = useMemo(() => ({ tenantId }), [tenantId]);

  const value = useMemo<IsoContextValue>(
    () => ({
      aspectos,
      riesgos,
      equipos,
      plantas,
      cargando,
      truncado,
      error,
      recargar,

      crearAspecto: (d) =>
        escribir(() => api.post('/iso14001/aspects', d, opts), 'Aspecto creado.'),
      editarAspecto: (id, d) =>
        escribir(() => api.patch(`/iso14001/aspects/${id}`, d, opts), 'Aspecto actualizado.'),
      borrarAspecto: (id) =>
        escribir(() => api.delete(`/iso14001/aspects/${id}`, opts), 'Aspecto eliminado.'),

      crearRiesgo: (d) =>
        escribir(() => api.post('/iso14001/risks', d, opts), 'Registro creado.'),
      editarRiesgo: (id, d) =>
        escribir(() => api.patch(`/iso14001/risks/${id}`, d, opts), 'Registro actualizado.'),
      borrarRiesgo: (id) =>
        escribir(() => api.delete(`/iso14001/risks/${id}`, opts), 'Registro eliminado.'),

      crearEquipo: (d) =>
        escribir(() => api.post('/iso14001/equipment', d, opts), 'Equipo creado.'),
      editarEquipo: (id, d) =>
        escribir(() => api.patch(`/iso14001/equipment/${id}`, d, opts), 'Equipo actualizado.'),
      borrarEquipo: (id) =>
        escribir(() => api.delete(`/iso14001/equipment/${id}`, opts), 'Equipo eliminado.'),
    }),
    [aspectos, riesgos, equipos, plantas, cargando, truncado, error, recargar, escribir, opts],
  );

  return <IsoContext.Provider value={value}>{children}</IsoContext.Provider>;
}

export function useIso(): IsoContextValue {
  const ctx = useContext(IsoContext);
  if (!ctx) throw new Error('useIso debe usarse dentro de <IsoProvider>');
  return ctx;
}
