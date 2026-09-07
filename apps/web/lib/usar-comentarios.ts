'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

/** Un comentario del hilo de un registro (RF-111). */
export interface Comentario {
  id: string;
  autorId: string;
  autor: string | null;
  cuerpo: string;
  padreId: string | null;
  /** No nulo si se editó después de publicarse. **Se muestra.** */
  editadoEl: string | null;
  menciones: string[];
  creadoEl: string;
}

export interface HiloDeComentarios {
  /**
   * `null` mientras no se sabe. **No es una lista vacía.**
   *
   * Un hilo vacío dice «nadie dijo nada sobre esto», que es una afirmación; una
   * consulta que no volvió no dice nada. Este proyecto confundió las dos cosas
   * cuatro veces antes de aprenderlo.
   */
  comentarios: Comentario[] | null;
  error: string | null;
  /** El motivo por el que no se puede comentar, o `null` si sí se puede. */
  publicando: boolean;
  publicar: (cuerpo: string, opciones?: { padreId?: string }) => Promise<boolean>;
  errorAlPublicar: string | null;
}

function mapear(f: Record<string, unknown>): Comentario {
  return {
    id: String(f.id),
    autorId: String(f.author_user_id),
    autor: f.author_name == null ? null : String(f.author_name),
    cuerpo: String(f.body ?? ''),
    padreId: f.parent_id == null ? null : String(f.parent_id),
    editadoEl: f.edited_at == null ? null : String(f.edited_at),
    menciones: Array.isArray(f.menciones) ? f.menciones.map(String) : [],
    creadoEl: String(f.created_at ?? ''),
  };
}

/**
 * El hilo de un registro, y la forma de agregarle algo.
 *
 * Una sola ruta para las trece entidades comentables: `entityType` dice cuál.
 * Es el mismo mapa que valida los vínculos documentales
 * (`services/vinculos_de_documentos.py::ANCLAJES`), a propósito — con dos
 * listas, una entidad comentable y no vinculable sería un estado que nadie
 * eligió.
 */
export function usarComentarios(
  entityType: string,
  entityId: string,
): HiloDeComentarios {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [comentarios, setComentarios] = useState<Comentario[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [publicando, setPublicando] = useState(false);
  const [errorAlPublicar, setErrorAlPublicar] = useState<string | null>(null);
  const [recargas, setRecargas] = useState(0);

  useEffect(() => {
    // Sin tenant se sale **sin borrar** lo que ya se sabía: la sesión pasa por
    // `null` mientras se resuelve, y limpiar acá hace que el hilo aparezca y
    // desaparezca solo. Es el defecto que ya apareció en `iso-store`.
    if (!tenantId || !entityId) return;
    let vigente = true;

    const consulta = new URLSearchParams({
      entity_type: entityType,
      entity_id: entityId,
    });

    api
      .get<Record<string, unknown>[]>(`/comentarios/?${consulta}`, { tenantId })
      .then((filas) => {
        if (!vigente) return;
        setError(null);
        setComentarios((Array.isArray(filas) ? filas : []).map(mapear));
      })
      .catch((e: unknown) => {
        if (!vigente) return;
        setError(mensajeDeError(e));
        setComentarios([]);
      });

    return () => {
      vigente = false;
    };
  }, [entityType, entityId, tenantId, recargas]);

  const publicar = useCallback(
    async (cuerpo: string, opciones?: { padreId?: string }) => {
      if (!tenantId) return false;
      setPublicando(true);
      setErrorAlPublicar(null);
      try {
        await api.post(
          '/comentarios/',
          {
            entity_type: entityType,
            entity_id: entityId,
            body: cuerpo,
            parent_id: opciones?.padreId ?? null,
          },
          { tenantId },
        );
        // Se recarga el hilo entero en vez de agregar la fila a mano: el
        // servidor decide el orden y resuelve el nombre del autor, y una copia
        // local terminaría discrepando de lo que se ve al recargar.
        setRecargas((n) => n + 1);
        return true;
      } catch (e: unknown) {
        // **Lo escrito se queda**: quien lo escribió no tiene por qué
        // redactarlo de nuevo porque el servidor respondió mal.
        setErrorAlPublicar(mensajeDeError(e));
        return false;
      } finally {
        setPublicando(false);
      }
    },
    [entityType, entityId, tenantId],
  );

  return { comentarios, error, publicando, publicar, errorAlPublicar };
}
