'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Contrato, SubTenant } from '@ambienta/shared';
import { mockSubTenants, mockContratos } from '@/mocks/gestores';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api } from '@/lib/api-client';

interface GestoresContextValue {
  subTenants: SubTenant[];
  contratos: Contrato[];
  loading: boolean;
  addContrato: (input: {
    subTenantId: string;
    nombre: string;
    fechaInicio: string;
    fechaTermino: string;
    camposCustom: Record<string, string>;
  }) => void;
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
  const [subTenants] = useState<SubTenant[]>(mockSubTenants);
  const [contratos, setContratos] = useState<Contrato[]>(mockContratos);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) {
      setLoading(false);
      return;
    }
    let cancelado = false;
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
      .catch(() => {})
      .finally(() => {
        if (!cancelado) setLoading(false);
      });
    return () => {
      cancelado = true;
    };
  }, [user?.tenantId]);

  /**
   * **Esto no llega a la base, y la causa está arriba de este store.**
   *
   * `POST /contracts/` exige `client_tenant_id`, y el `subTenantId` que llega
   * acá sale de `mockSubTenants` — este store **nunca pide los sub-tenants a la
   * API**, porque la sub-tenancy (RF-65) no está implementada: no hay endpoint
   * que los liste. Mandar un id de dato de ejemplo da 422, porque la referencia
   * se valida contra lo visible bajo RLS.
   *
   * O sea: el contrato no se puede guardar hasta que existan los sub-tenants
   * contra los cuales se firma. La lectura de contratos sí funciona y es real.
   *
   * Faltan además `contract_number` y `manager_tenant_id`; los dos son
   * derivables, pero no arreglan lo anterior.
   */
  function addContrato(input: {
    subTenantId: string;
    nombre: string;
    fechaInicio: string;
    fechaTermino: string;
    camposCustom: Record<string, string>;
  }) {
    const nuevo: Contrato = {
      id: `contrato-${Date.now()}`,
      subTenantId: input.subTenantId,
      nombre: input.nombre,
      fechaInicio: input.fechaInicio,
      fechaTermino: input.fechaTermino,
      camposCustom: input.camposCustom,
    };
    setContratos((prev) => [...prev, nuevo]);

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
  }

  return (
    <GestoresContext.Provider value={{ subTenants, contratos, loading, addContrato }}>
      {children}
    </GestoresContext.Provider>
  );
}

export function useGestores() {
  const ctx = useContext(GestoresContext);
  if (!ctx) throw new Error('useGestores debe usarse dentro de <GestoresProvider>');
  return ctx;
}
