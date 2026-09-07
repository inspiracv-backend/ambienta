'use client';

import { useEffect, useState } from 'react';
import type { EntidadAuditable } from '@ambienta/shared';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';
import { tipoEnLaApi } from '@/lib/vocabulario-de-entidades';

/** Un hecho de la historia de un registro, como lo devuelve la API. */
export interface EventoDeHistoria {
  tipo: 'actividad' | 'comentario' | 'adjunto';
  ocurridoEl: string;
  actor: string | null;
  resumen: string;
  detalle: Record<string, unknown>;
}

export interface Historia {
  /**
   * `null` mientras no se sabe. **No es una lista vacía.**
   *
   * Una historia vacía dice «sobre este registro no pasó nada»; una consulta
   * que no volvió no dice nada. Y acá la diferencia es más filosa que de
   * costumbre: hasta hoy este historial se veía vacío **siempre**, porque el
   * store nunca preguntaba.
   */
  eventos: EventoDeHistoria[] | null;
  error: string | null;
  /**
   * Los orígenes que RF-113 nombra y todavía no existen. Hoy: el correo.
   *
   * Se muestra. Una línea de tiempo sin correos que no lo advierte hace
   * concluir que no hubo correos.
   */
  fuentesPendientes: string[];
  /** `true` si se alcanzó el tope y hay historia anterior sin traer. */
  hayMas: boolean;
}

/**
 * La historia de un registro, desde la API.
 *
 * Traduce el nombre en español que usa la aplicación al de dominio que entiende
 * la API (`obligacion` → `obligation`). Para las entidades que no tienen
 * equivalente —usuario, empresa, departamento, planta— **no consulta nada** y
 * devuelve una lista vacía sin error: no es un fallo, es que esa entidad no
 * tiene historia del otro lado. Ver `lib/vocabulario-de-entidades.ts`.
 */
export function usarHistoria(entidad: EntidadAuditable, entidadId: string): Historia {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [eventos, setEventos] = useState<EventoDeHistoria[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fuentesPendientes, setFuentesPendientes] = useState<string[]>([]);
  const [hayMas, setHayMas] = useState(false);

  useEffect(() => {
    const tipo = tipoEnLaApi(entidad);
    if (tipo === null) {
      // Esa entidad no tiene historia en la API, y eso es una respuesta.
      setEventos([]);
      setError(null);
      return;
    }
    // Sin tenant se sale **sin borrar** lo que ya se sabía: la sesión pasa por
    // `null` mientras se resuelve, y limpiar acá hace que la línea de tiempo
    // aparezca y desaparezca sola.
    if (!tenantId || !entidadId) return;
    let vigente = true;

    const consulta = new URLSearchParams({
      entity_type: tipo,
      entity_id: entidadId,
    });

    api
      .get<Record<string, unknown>>(`/historial/?${consulta}`, { tenantId })
      .then((cuerpo) => {
        if (!vigente) return;
        setError(null);
        const crudos = Array.isArray(cuerpo?.eventos) ? cuerpo.eventos : [];
        setEventos(
          (crudos as Record<string, unknown>[]).map((e) => ({
            tipo: String(e.tipo) as EventoDeHistoria['tipo'],
            ocurridoEl: String(e.ocurrido_el ?? ''),
            actor: e.actor == null ? null : String(e.actor),
            resumen: String(e.resumen ?? ''),
            detalle: (e.detalle as Record<string, unknown>) ?? {},
          })),
        );
        setFuentesPendientes(
          Array.isArray(cuerpo?.fuentes_pendientes)
            ? (cuerpo.fuentes_pendientes as unknown[]).map(String)
            : [],
        );
        setHayMas(Boolean(cuerpo?.hay_mas));
      })
      .catch((e: unknown) => {
        if (!vigente) return;
        setError(mensajeDeError(e));
        setEventos([]);
      });

    return () => {
      vigente = false;
    };
  }, [entidad, entidadId, tenantId]);

  return { eventos, error, fuentesPendientes, hayMas };
}
