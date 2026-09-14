'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Contrato, SubTenant } from '@ambienta/shared';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api, mensajeDeError } from '@/lib/api-client';

interface GestoresContextValue {
  subTenants: SubTenant[];
  contratos: Contrato[];
  loading: boolean;
  /**
   * Por que la lista esta vacia, si es que fallo (#208).
   *
   * `null` = se pregunto y esto es lo que hay. Un texto = **no se pudo
   * preguntar**, y la pantalla tiene que decirlo: sin esto un fallo de red se
   * ve igual que "esta empresa no tiene ninguno".
   */
  errorDeCarga: string | null;
  /** Por que fallo el ultimo intento de guardar. `null` = no fallo. */
  errorAlGuardar: string | null;
  /** `false` si la API lo rechazo: la lista no se toca y la pantalla lo dice. */
  addContrato: (input: {
    subTenantId: string;
    numero: string;
    nombre: string;
    fechaInicio: string;
    fechaTermino: string;
    camposCustom: Record<string, string>;
  }) => Promise<boolean>;
}

const GestoresContext = createContext<GestoresContextValue | null>(null);

/**
 * `subTenantId` sale de `client_tenant_id`: en la API el contrato nombra a las
 * dos partes —la gestora y su cliente— y desde la sesión de la gestora el
 * "sub-tenant" es el cliente.
 *
 * `camposCustom` sale de `scope`, que es el jsonb libre del contrato. No se
 * usa `terms_snapshot`: ese guarda las condiciones congeladas de la firma, y
 * mostrarlo como campos editables invitaría a cambiarlo.
 */
function mapApiContrato(raw: Record<string, unknown>): Contrato | null {
  try {
    const scope = (raw.scope ?? {}) as Record<string, unknown>;
    return {
      id: String(raw.id),
      subTenantId: String(raw.client_tenant_id ?? ''),
      nombre: String(raw.title ?? raw.contract_number ?? ''),
      fechaInicio: String(raw.start_date ?? ''),
      fechaTermino: raw.end_date ? String(raw.end_date) : '',
      camposCustom: Object.fromEntries(
        Object.entries(scope).map(([k, v]) => [k, String(v)]),
      ),
    };
  } catch {
    return null;
  }
}

export function GestoresProvider({ children }: { children: ReactNode }) {
  // **Sale de la API desde el 10-sep.** Este comentario decia que no habia
  // endpoint que listara sub-tenants, y era cierto hasta que el bloque C cerro:
  // `GET /gestor/clientes` devuelve la cartera real. La nota se quedo vieja.
  //
  // Lo que sigue valiendo es el resto: **nunca datos de ejemplo** (#208).
  // Ensenarle a un Gestor una cartera inventada, con nombres y RUT de empresas
  // que no existen, en la pantalla que se usa para decidir a quien facturar,
  // es peor que ensenarle una lista vacia.
  const [subTenants, setSubTenants] = useState<SubTenant[]>([]);
  const [contratos, setContratos] = useState<Contrato[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const [errorAlGuardar, setErrorAlGuardar] = useState<string | null>(null);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) {
      setLoading(false);
      return;
    }
    let cancelado = false;

    /**
     * La cartera del gestor.
     *
     * **Se pide aparte de los contratos y su fallo no tumba la pantalla.** Una
     * empresa que no es gestora recibe **403** en esta ruta, y eso no es un
     * error que mostrar: es la respuesta correcta a "¿cuál es tu cartera?"
     * cuando no se administra a nadie. Tratarlo como fallo dejaría un cartel
     * rojo en la pantalla de cualquiera.
     */
    const cartera = api
      .get<Record<string, unknown>[]>('/gestor/clientes', { tenantId: user.tenantId })
      .catch(() => [] as Record<string, unknown>[]);

    cartera.then((clientes) => {
      if (cancelado) return;
      setSubTenants(
        clientes.map((c) => ({
          id: String(c.tenant_id),
          gestorTenantId: user.tenantId!,
          nombre: String(c.legal_name ?? ''),
          // La empresa retirada llega sin RUT: se dice, en vez de dejar la
          // celda vacía, que se leería como que esa empresa no tiene.
          rut: c.rut ? String(c.rut) : 'Sin RUT registrado',
          // `puede_actuar` ya resuelve las dos condiciones —contrato `active`
          // y dentro de sus fechas— en el servidor. Repetir el criterio acá
          // sería la tercera copia de una regla que ya vive en un solo lugar.
          estado: c.puede_actuar ? 'activo' : 'inactivo',
          // **No hay endpoint que traiga los contactos de un cliente desde el
          // gestor.** Queda vacío y la tabla lo dice como «—», no como «0»:
          // un cero afirma que ese cliente no tiene a nadie con quien hablar.
          contactos: [],
        })),
      );
    });

    api
      .get<Record<string, unknown>[]>('/contracts/', { tenantId: user.tenantId })
      .then((data) => {
        if (cancelado) return;
        const mapeados = data
          .map(mapApiContrato)
          .filter((c): c is Contrato => c !== null);
        // **Se escribe siempre, incluso vacio** (#208). El `if (length > 0)`
        // de antes no distinguia dos cosas muy distintas: que la API fallara
        // —donde quedarse con lo que hay es un respaldo razonable— y que
        // respondiera **cero filas**, donde quedarse con los datos de ejemplo
        // es mostrar algo que no existe.
        //
        // El `catch` sigue conservando lo ultimo conocido, asi que trabajar sin
        // backend levantado sigue funcionando: ahi la peticion falla, no
        // devuelve vacio.
        setContratos(mapeados);
      })
      .catch((e: unknown) => {
        // **Se dice que fallo.** Con la lista vacia y sin mensaje, la
        // pantalla afirma 'no hay nada' cuando la verdad es 'no se pudo
        // preguntar' — que es la misma mentira de #208 en su otra forma.
        setErrorDeCarga(mensajeDeError(e));
      })
      .finally(() => {
        if (!cancelado) setLoading(false);
      });
    return () => {
      cancelado = true;
    };
  }, [user?.tenantId]);

  /**
   * Registra un contrato con un cliente. **Ahora sí llega a la base.**
   *
   * ## Lo que la desbloqueó
   *
   * Acá decía que `POST /contracts/` exige `client_tenant_id` y que este store
   * nunca pedía los sub-tenants «porque la sub-tenancy (RF-65) no está
   * implementada: no hay endpoint que los liste». Era cierto — y **dejó de
   * serlo cuando cerró el bloque C**: `GET /gestor/clientes` devuelve la
   * cartera. La nota se quedó vieja, igual que la de `addNorm`.
   *
   * ## `numero` se pide, no se inventa
   *
   * `contract_number` es `NOT NULL` y único por gestor, y el formulario no lo
   * tenía. Derivarlo —`CTR-2026-0001`— habría sido más corto y habría puesto en
   * el sistema un identificador que **no coincide con el del papel firmado**.
   * Es el mismo criterio que la `periodicidad` vacía de `retc_systems`: se
   * construye el mecanismo, no se inventa el contenido.
   *
   * ## Devuelve si se guardó
   *
   * Y no toca la lista si falló. El número duplicado es un rechazo esperable
   * —la restricción es `UNIQUE (manager_tenant_id, contract_number)`— y la
   * pantalla tiene que poder decirlo en vez de mostrar un contrato que no está.
   */
  async function addContrato(input: {
    subTenantId: string;
    numero: string;
    nombre: string;
    fechaInicio: string;
    fechaTermino: string;
    camposCustom: Record<string, string>;
  }): Promise<boolean> {
    if (!user?.tenantId) return false;

    let creado: Record<string, unknown>;
    try {
      creado = await api.post<Record<string, unknown>>(
        '/contracts/',
        {
          manager_tenant_id: user.tenantId,
          client_tenant_id: input.subTenantId,
          contract_number: input.numero,
          title: input.nombre,
          // La API espera fechas de calendario (`date`), no marcas de tiempo:
          // mandar el ISO completo con hora es cómo una fecha retrocede un día
          // al oeste de Greenwich — el defecto que ya apareció en documentos.
          start_date: input.fechaInicio.slice(0, 10),
          end_date: input.fechaTermino ? input.fechaTermino.slice(0, 10) : null,
          scope: input.camposCustom,
        },
        { tenantId: user.tenantId },
      );
    } catch (e) {
      setErrorAlGuardar(mensajeDeError(e));
      return false;
    }

    const nuevo: Contrato =
      mapApiContrato(creado) ?? {
        id: String(creado.id),
        subTenantId: input.subTenantId,
        nombre: input.nombre,
        fechaInicio: input.fechaInicio,
        fechaTermino: input.fechaTermino,
        camposCustom: input.camposCustom,
      };
    setContratos((prev) => [...prev, nuevo]);
    setErrorAlGuardar(null);

    const subTenant = subTenants.find((s) => s.id === input.subTenantId);

    registrar({
      entidadTipo: 'contrato',
      entidadId: nuevo.id,
      entidadLabel: `${nuevo.nombre} — ${subTenant?.nombre ?? input.subTenantId}`,
      accion: 'creado',
      resumen: `Creó el contrato con ${subTenant?.nombre ?? 'el cliente'}`,
      cambios: [
        { campo: 'Vigencia', antes: null, despues: `${input.fechaInicio} a ${input.fechaTermino}` },
        ...(Object.keys(input.camposCustom).length > 0
          ? [{ campo: 'Campos adicionales', antes: null, despues: Object.keys(input.camposCustom).join(', ') }]
          : []),
      ],
    });
    return true;
  }

  return (
    <GestoresContext.Provider value={{ subTenants, contratos, loading, errorDeCarga, errorAlGuardar, addContrato }}>
      {children}
    </GestoresContext.Provider>
  );
}

export function useGestores() {
  const ctx = useContext(GestoresContext);
  if (!ctx) throw new Error('useGestores debe usarse dentro de <GestoresProvider>');
  return ctx;
}
