'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';
import {
  mapEtapa,
  mapPersona,
  mapTrato,
  type EtapaCrm,
  type PersonaAsignable,
  type TipoDeEtapa,
} from '@/lib/crm';
import type { Resultado } from '@/lib/crm-empresas-store';

/**
 * Las etapas del pipeline y quién puede hacerse cargo de un trato.
 *
 * ## Por qué las etapas necesitan pantalla propia
 *
 * Son configurables por empresa a propósito (#78): una consultora ambiental y
 * un gestor de residuos no venden igual. Pero la configuración vivía solo en la
 * API, así que en la práctica todas las empresas tenían el mismo pipeline y la
 * única forma de cambiarlo era por `curl`.
 *
 * ## Y por qué el store cuenta los tratos por etapa
 *
 * Retirar una columna con tratos dentro los deja fuera del tablero sin
 * borrarlos, y el servidor lo rechaza con 409. Para poder decirlo **antes** de
 * que alguien lo intente hay que saber cuántos hay, y eso sale del pipeline —
 * que además ya trae el total del servidor y no el de las tarjetas visibles.
 */

const TOPE = 500;

export interface DatosDeEtapa {
  codigo: string;
  nombre: string;
  posicion: number;
  tipo: TipoDeEtapa;
}

export function useEtapasDelPipeline() {
  const { user } = useSession();
  const [etapas, setEtapas] = useState<EtapaCrm[]>([]);
  /** Cuántos tratos vivos hay en cada etapa, por id. */
  const [tratosPorEtapa, setTratosPorEtapa] = useState<Record<string, number>>({});
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
    const opciones = { tenantId: user.tenantId };
    try {
      const crudas = await api.get<Record<string, unknown>[]>('/crm/stages', opciones);
      if (!vigente.current) return;
      setEtapas(crudas.map(mapEtapa));
      setErrorDeCarga(null);
    } catch (e) {
      if (!vigente.current) return;
      setEtapas([]);
      setErrorDeCarga(mensajeDeError(e));
      setCargando(false);
      return;
    }

    // El conteo va aparte y **su fallo no impide configurar**: sin él no se
    // puede avisar por adelantado cuántos tratos hay dentro, pero el servidor
    // sigue rechazando el retiro igual. Colapsarlo con la carga de etapas
    // dejaría la pantalla vacía por un dato accesorio.
    try {
      const tratos = await api.get<Record<string, unknown>[]>(
        `/crm/deals?limit=${TOPE}`,
        opciones,
      );
      if (!vigente.current) return;
      const cuenta: Record<string, number> = {};
      for (const t of tratos.map(mapTrato)) {
        cuenta[t.etapaId] = (cuenta[t.etapaId] ?? 0) + 1;
      }
      setTratosPorEtapa(cuenta);
    } catch {
      if (vigente.current) setTratosPorEtapa({});
    } finally {
      if (vigente.current) setCargando(false);
    }
  }, [user?.tenantId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const crear = useCallback(
    async (datos: DatosDeEtapa): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        await api.post(
          '/crm/stages',
          {
            code: datos.codigo.trim(),
            name: datos.nombre.trim(),
            position: datos.posicion,
            kind: datos.tipo,
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

  const editar = useCallback(
    async (id: string, datos: Partial<DatosDeEtapa>): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        // `code` **no se manda**: es el identificador estable de la etapa y la
        // API no lo acepta en el `PATCH`. Renombrar cambia `name`.
        await api.patch(
          `/crm/stages/${id}`,
          {
            ...(datos.nombre !== undefined ? { name: datos.nombre.trim() } : {}),
            ...(datos.posicion !== undefined ? { position: datos.posicion } : {}),
            ...(datos.tipo !== undefined ? { kind: datos.tipo } : {}),
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

  const retirar = useCallback(
    async (id: string): Promise<Resultado> => {
      if (!user?.tenantId) return { ok: false, error: 'Sin sesión.' };
      try {
        await api.delete(`/crm/stages/${id}`, { tenantId: user.tenantId });
        await cargar();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: mensajeDeError(e) };
      }
    },
    [user?.tenantId, cargar],
  );

  return { etapas, tratosPorEtapa, cargando, errorDeCarga, crear, editar, retirar, recargar: cargar };
}

/**
 * Las personas de la empresa, para asignar responsables.
 *
 * **Pide `/users/` en vez de usar `useUsers()`**, que arranca con `mockUsers` y
 * se queda con ellos cuando la API falla. Un selector construido sobre ese store
 * ofrecería gente que no existe en la base, y `owner_user_id` es una clave
 * foránea: la escritura respondería 422 sin que se entienda por qué. Es el mismo
 * error que ya se cometió con el selector de plantas.
 */
export function usePersonasAsignables() {
  const { user } = useSession();
  const [personas, setPersonas] = useState<PersonaAsignable[]>([]);
  const [cargando, setCargando] = useState(true);
  const [fallo, setFallo] = useState(false);

  useEffect(() => {
    let vigente = true;
    if (!user?.tenantId) {
      setCargando(false);
      return;
    }
    void (async () => {
      try {
        const crudas = await api.get<Record<string, unknown>[]>(
          `/users/?limit=${TOPE}`,
          { tenantId: user.tenantId },
        );
        if (!vigente) return;
        setPersonas(crudas.map(mapPersona));
        setFallo(false);
      } catch {
        if (!vigente) return;
        // Lista vacía y `fallo` en true: la pantalla dice que no se pudo traer
        // la gente, en vez de mostrar un selector vacío que se lee como «esta
        // empresa no tiene a nadie».
        setPersonas([]);
        setFallo(true);
      } finally {
        if (vigente) setCargando(false);
      }
    })();
    return () => {
      vigente = false;
    };
  }, [user?.tenantId]);

  return { personas, cargando, fallo };
}
