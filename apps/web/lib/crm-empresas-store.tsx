'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';
import {
  mapActividad,
  mapContacto,
  mapEmpresa,
  mapEtapa,
  mapTrato,
  type ActividadCrm,
  type ContactoCrm,
  type EmpresaCrm,
  type EstadoDeEmpresa,
  type EtapaCrm,
  type TipoDeActividad,
  type TratoCrm,
} from '@/lib/crm';

/**
 * Empresas, contactos, tratos y actividades del CRM.
 *
 * Sigue el criterio de `crm-store`: **hook por pantalla y no provider global**.
 * El CRM lo mira quien vende, no quien evalúa una norma, así que montarlo
 * arriba del dashboard haría una petición de más en las otras veinte pantallas.
 *
 * Y tampoco cae a datos de ejemplo cuando la API falla. En un módulo comercial
 * el daño de un respaldo falso es directo: quien ve una empresa en la lista
 * asume que existe, y puede llamarla.
 */

/** Cuántas filas pedir donde hay que filtrar en el navegador. Es el tope duro
 *  del servidor (`TOPE_DE_PAGINA`); pedir más responde 422. */
const TOPE = 500;

export interface DatosDeEmpresa {
  nombre: string;
  /** Quien esta a cargo. `null` = sin responsable, que no es lo mismo que
   *  «alguien que no reconocemos» — ver `nombreDelResponsable`. */
  responsableId?: string | null;
  rut?: string | null;
  rubro?: string | null;
  sitioWeb?: string | null;
  estado?: EstadoDeEmpresa;
  notas?: string | null;
}

export interface DatosDeContacto {
  nombre: string;
  correo?: string | null;
  telefono?: string | null;
  cargo?: string | null;
  esPrincipal?: boolean;
}

export interface DatosDeActividad {
  tipo: TipoDeActividad;
  asunto: string;
  detalle?: string | null;
}

/** Lo que se puede corregir de una actividad ya anotada.
 *
 *  **El padre no**: mover una llamada de un trato a otro reescribiria dos
 *  lineas de tiempo a la vez, y la API tampoco lo acepta. Se anota de nuevo en
 *  el sitio correcto y se retira la equivocada. */
export interface CorreccionDeActividad {
  asunto: string;
  detalle?: string | null;
}

export interface DatosDeTrato {
  titulo: string;
  responsableId?: string | null;
  monto?: string | null;
  moneda?: string;
  contactoId?: string | null;
  cierreEstimado?: string | null;
}

/** Lo que devuelve una escritura: si funcionó y, si no, por qué. */
export interface Resultado {
  ok: boolean;
  error?: string;
  /** Lo que el servidor dice que pasó además de lo pedido. Mover un trato puede
   *  cerrarlo; promoverlo puede convertir la ficha en cliente. */
  efectos?: string[];
}

function aCuerpoDeEmpresa(datos: DatosDeEmpresa): Record<string, unknown> {
  // Los vacíos van como `null` y no como cadena vacía: la diferencia entre
  // "no tiene RUT" y "tiene el RUT ''" existe en la base y se pierde acá si no
  // se cuida.
  return {
    name: datos.nombre,
    rut: datos.rut?.trim() || null,
    industry: datos.rubro?.trim() || null,
    website: datos.sitioWeb?.trim() || null,
    status: datos.estado ?? 'prospect',
    owner_user_id: datos.responsableId || null,
    notes: datos.notas?.trim() || null,
  };
}

function aCuerpoDeTrato(datos: DatosDeTrato): Record<string, unknown> {
  return {
    title: datos.titulo.trim(),
    // **Se manda como string, no como número.** `amount` es un `numeric` de
    // Postgres y Pydantic lo recibe como `Decimal`: convertirlo a número de
    // JavaScript en el camino pierde precisión en montos grandes, que en un
    // pipeline es plata que nadie va a cuadrar después.
    amount: datos.monto?.trim() || null,
    currency: datos.moneda?.trim() || 'CLP',
    crm_contact_id: datos.contactoId || null,
    owner_user_id: datos.responsableId || null,
    expected_close_date: datos.cierreEstimado?.trim() || null,
  };
}

export function useCrmEmpresas() {
  const { user } = useSession();
  const [empresas, setEmpresas] = useState<EmpresaCrm[]>([]);
  const [hayMas, setHayMas] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const vigente = useRef(true);

  useEffect(() => {
    vigente.current = true;
    return () => {
      vigente.current = false;
    };
  }, []);

  const cargar = useCallback(async () => {
    if (!user?.tenantId) {
      setCargando(false);
      return;
    }
    setCargando(true);
    try {
      // `getPagina` y no `get`: la API acota los listados y avisa por cabecera
      // cuando cortó (#167). Una cartera de 500 de 640 se ve perfectamente
      // normal, y ese es justo el defecto.
      const { datos, hayMas: cortada } = await api.getPagina<Record<string, unknown>>(
        `/crm/companies?limit=${TOPE}`,
        { tenantId: user.tenantId },
      );
      if (!vigente.current) return;
      setEmpresas(datos.map(mapEmpresa));
      setHayMas(cortada);
      setErrorDeCarga(null);
    } catch (e) {
      if (!vigente.current) return;
      // Vacío, no lo último conocido: una lista que sobrevive a una petición
      // fallida se lee como el estado actual de la cartera.
      setEmpresas([]);
      setHayMas(false);
      setErrorDeCarga(mensajeDeError(e));
    } finally {
      if (vigente.current) setCargando(false);
    }
  }, [user?.tenantId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const crear = useCallback(
    async (datos: DatosDeEmpresa): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        await api.post('/crm/companies', aCuerpoDeEmpresa(datos), {
          tenantId: user.tenantId,
        });
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  const editar = useCallback(
    async (id: string, datos: DatosDeEmpresa): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        await api.patch(`/crm/companies/${id}`, aCuerpoDeEmpresa(datos), {
          tenantId: user.tenantId,
        });
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  const retirar = useCallback(
    async (id: string): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        // Borrado logico: sus tratos y actividades se conservan, porque son el
        // historial de por que se dejo de trabajar con ella.
        await api.delete(`/crm/companies/${id}`, { tenantId: user.tenantId });
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  return { empresas, hayMas, cargando, errorDeCarga, crear, editar, retirar, recargar: cargar };
}

/**
 * Todo lo de UNA empresa: su ficha, sus contactos, sus tratos y su línea de
 * tiempo.
 *
 * ## Un fallo de una parte no vacía a las otras
 *
 * Las peticiones van juntas y cada una guarda su propio error: si los contactos
 * cargan y las actividades no, la ficha muestra los contactos y dice que la
 * línea de tiempo no se pudo traer. Colapsar las cuatro en un solo mensaje
 * escondería información que sí llegó.
 *
 * ## Contactos y tratos se filtran en el navegador, y hay que decirlo
 *
 * `/crm/contacts` y `/crm/deals` **no aceptan filtro por empresa**: devuelven la
 * lista de la empresa que usa el sistema, acotada al tope del servidor. Se pide
 * el tope y se filtra acá, pero si la respuesta vino cortada, "esta empresa no
 * tiene contactos" puede ser falso — y eso se muestra en pantalla en vez de
 * dejar una sección vacía que se lee como un hecho.
 *
 * Las actividades sí las filtra el servidor, y además incluye las de los tratos
 * y contactos de la empresa: quien abre una ficha quiere ver todo lo que pasó
 * con ella, no la parte que alguien recordó anotar en el sitio exacto.
 */
export function useFichaDeEmpresa(empresaId: string | null) {
  const { user } = useSession();
  const [empresa, setEmpresa] = useState<EmpresaCrm | null>(null);
  const [contactos, setContactos] = useState<ContactoCrm[]>([]);
  const [tratos, setTratos] = useState<TratoCrm[]>([]);
  const [etapas, setEtapas] = useState<EtapaCrm[]>([]);
  const [actividades, setActividades] = useState<ActividadCrm[]>([]);
  const [listasCortadas, setListasCortadas] = useState<string[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const vigente = useRef(true);

  useEffect(() => {
    vigente.current = true;
    return () => {
      vigente.current = false;
    };
  }, []);

  const cargar = useCallback(async () => {
    if (!user?.tenantId || !empresaId) {
      setCargando(false);
      return;
    }
    setCargando(true);
    const opciones = { tenantId: user.tenantId };
    const fallos: Record<string, string> = {};
    const cortadas: string[] = [];

    const pedir = async <T,>(
      clave: string,
      ruta: string,
      aplicar: (filas: Record<string, unknown>[]) => T,
    ): Promise<T | null> => {
      try {
        const raw = await api.get<Record<string, unknown>[]>(ruta, opciones);
        return aplicar(raw);
      } catch (e) {
        fallos[clave] = mensajeDeError(e);
        return null;
      }
    };

    const pedirPagina = async <T,>(
      clave: string,
      etiqueta: string,
      ruta: string,
      aplicar: (filas: Record<string, unknown>[]) => T,
    ): Promise<T | null> => {
      try {
        const { datos, hayMas } = await api.getPagina<Record<string, unknown>>(
          ruta,
          opciones,
        );
        if (hayMas) cortadas.push(etiqueta);
        return aplicar(datos);
      } catch (e) {
        fallos[clave] = mensajeDeError(e);
        return null;
      }
    };

    // La ficha va con su propia función porque su respuesta es un objeto y no
    // un arreglo; sale en el mismo `Promise.all` para no encadenar una espera
    // más antes de que la pantalla tenga con qué dibujarse.
    const pedirFicha = async (): Promise<EmpresaCrm | null> => {
      try {
        const raw = await api.get<Record<string, unknown>>(
          `/crm/companies/${empresaId}`,
          opciones,
        );
        return mapEmpresa(raw);
      } catch (e) {
        fallos.empresa = mensajeDeError(e);
        return null;
      }
    };

    const [fichaEmpresa, cts, trs, etps, acts] = await Promise.all([
      pedirFicha(),
      pedirPagina('contactos', 'contactos', `/crm/contacts?limit=${TOPE}`, (f) =>
        f.map(mapContacto).filter((x) => x.empresaId === empresaId),
      ),
      pedirPagina('tratos', 'oportunidades', `/crm/deals?limit=${TOPE}`, (f) =>
        f.map(mapTrato).filter((x) => x.empresaId === empresaId),
      ),
      pedir('etapas', '/crm/stages', (f) => f.map(mapEtapa)),
      pedir('actividades', `/crm/activities?company_id=${empresaId}&limit=${TOPE}`, (f) =>
        f.map(mapActividad),
      ),
    ]);

    if (!vigente.current) return;
    setEmpresa(fichaEmpresa);
    setContactos(cts ?? []);
    setTratos(trs ?? []);
    setEtapas(etps ?? []);
    setActividades(acts ?? []);
    setListasCortadas(cortadas);
    setErrores(fallos);
    setCargando(false);
  }, [user?.tenantId, empresaId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const agregarContacto = useCallback(
    async (datos: DatosDeContacto): Promise<Resultado> => {
      if (!user?.tenantId || !empresaId) return { ok: false, error: 'Sin sesión.' };
      try {
        await api.post(
          '/crm/contacts',
          {
            crm_company_id: empresaId,
            full_name: datos.nombre.trim(),
            email: datos.correo?.trim() || null,
            phone: datos.telefono?.trim() || null,
            role_title: datos.cargo?.trim() || null,
            is_primary: Boolean(datos.esPrincipal),
          },
          { tenantId: user.tenantId },
        );
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, empresaId, cargar],
  );

  const editarContacto = useCallback(
    async (id: string, datos: DatosDeContacto): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        await api.patch(
          `/crm/contacts/${id}`,
          {
            full_name: datos.nombre.trim(),
            email: datos.correo?.trim() || null,
            phone: datos.telefono?.trim() || null,
            role_title: datos.cargo?.trim() || null,
            is_primary: Boolean(datos.esPrincipal),
          },
          { tenantId: user.tenantId },
        );
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  const registrarActividad = useCallback(
    async (datos: DatosDeActividad): Promise<Resultado> => {
      if (!user?.tenantId || !empresaId) return { ok: false, error: 'Sin sesión.' };
      try {
        // **Cuelga de la empresa y de nada más.** La base exige exactamente un
        // padre: mandar dos la rechaza, y mandar ninguno dejaría una actividad
        // que no aparece en ninguna ficha.
        await api.post(
          '/crm/activities',
          {
            kind: datos.tipo,
            subject: datos.asunto.trim(),
            body: datos.detalle?.trim() || null,
            crm_company_id: empresaId,
          },
          { tenantId: user.tenantId },
        );
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, empresaId, cargar],
  );

  const crearTrato = useCallback(
    async (datos: DatosDeTrato): Promise<Resultado> => {
      if (!user?.tenantId || !empresaId) return { ok: false, error: 'Sin sesión.' };
      try {
        // Sin `stage_id`: la API lo pone en la **primera etapa abierta** del
        // pipeline. Elegirla acá sería repetir esa regla en un segundo sitio, y
        // si alguien reordena y deja "Perdido" arriba, un trato nuevo nacería
        // perdido.
        await api.post(
          '/crm/deals',
          { crm_company_id: empresaId, ...aCuerpoDeTrato(datos) },
          { tenantId: user.tenantId },
        );
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, empresaId, cargar],
  );

  const editarTrato = useCallback(
    async (id: string, datos: DatosDeTrato): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        // `stage_id` **no va**: la etapa tiene su propio endpoint porque mover
        // de columna cierra el trato, exige motivo al perder o lo reabre, y
        // todo eso se perdería en un PATCH genérico.
        await api.patch(`/crm/deals/${id}`, aCuerpoDeTrato(datos), {
          tenantId: user.tenantId,
        });
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  const moverTrato = useCallback(
    async (id: string, etapaId: string, motivo?: string): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        const raw = await api.post<Record<string, unknown>>(
          `/crm/deals/${id}/stage`,
          { stage_id: etapaId, motivo: motivo?.trim() || null },
          { tenantId: user.tenantId },
        );
        await cargar();
        return {
          ok: true,
          efectos: Array.isArray(raw.efectos) ? raw.efectos.map(String) : [],
        };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  const editarActividad = useCallback(
    async (id: string, datos: CorreccionDeActividad): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        await api.patch(
          `/crm/activities/${id}`,
          { subject: datos.asunto.trim(), body: datos.detalle?.trim() || null },
          { tenantId: user.tenantId },
        );
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  /**
   * Retirar cualquier pieza de la ficha. Es borrado **logico** en las cuatro.
   *
   * Una sola funcion y no cuatro porque lo unico que cambia es la ruta, y
   * cuatro copias del mismo `try/catch` son cuatro sitios donde arreglar el
   * dia que el manejo de errores cambie.
   */
  const retirar = useCallback(
    async (
      que: 'contacts' | 'deals' | 'activities',
      id: string,
    ): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        await api.delete(`/crm/${que}/${id}`, { tenantId: user.tenantId });
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  const promover = useCallback(
    async (tratoId: string, contratoId: string): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        const raw = await api.post<Record<string, unknown>>(
          `/crm/deals/${tratoId}/promover`,
          { contract_id: contratoId },
          { tenantId: user.tenantId },
        );
        // Se recarga entera: promover cambia el trato **y la ficha** —la empresa
        // pasa a cliente y queda ligada al tenant—, y reconstruir eso acá sería
        // escribir por segunda vez una regla que ya vive en `services/crm.py`.
        await cargar();
        return {
          ok: true,
          efectos: Array.isArray(raw.efectos) ? raw.efectos.map(String) : [],
        };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  return {
    empresa,
    contactos,
    tratos,
    etapas,
    actividades,
    listasCortadas,
    cargando,
    errores,
    agregarContacto,
    editarContacto,
    registrarActividad,
    crearTrato,
    editarTrato,
    moverTrato,
    editarActividad,
    retirar,
    promover,
    recargar: cargar,
  };
}
