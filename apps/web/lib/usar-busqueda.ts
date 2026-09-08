'use client';

import { useCallback, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

export interface Coincidencia {
  tipo: string;
  id: string;
  titulo: string;
  codigo: string | null;
  contexto: Record<string, unknown>;
}

export interface GrupoDeResultados {
  tipo: string;
  coincidencias: Coincidencia[];
  /** `true` si el grupo se cortó y hay más sin traer. */
  hayMas: boolean;
}

export interface Busqueda {
  /**
   * `null` mientras **todavía no se buscó**. No es una lista vacía.
   *
   * En un buscador la diferencia se ve a cada rato: la pantalla arranca sin
   * resultados, y eso no significa «no hay coincidencias» — significa que
   * nadie preguntó nada todavía.
   */
  grupos: GrupoDeResultados[] | null;
  error: string | null;
  buscando: boolean;
  /** Lo que el buscador NO mira. Se muestra siempre que haya resultados. */
  advertencias: string[];
  buscar: (q: string) => Promise<void>;
}

/** El buscador transversal (RF-114). */
export function usarBusqueda(): Busqueda {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [grupos, setGrupos] = useState<GrupoDeResultados[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [advertencias, setAdvertencias] = useState<string[]>([]);

  const buscar = useCallback(
    async (q: string) => {
      if (!tenantId) return;
      setBuscando(true);
      setError(null);
      try {
        const cuerpo = await api.get<Record<string, unknown>>(
          `/buscar/?${new URLSearchParams({ q })}`,
          { tenantId },
        );
        const crudos = Array.isArray(cuerpo?.grupos) ? cuerpo.grupos : [];
        setGrupos(
          (crudos as Record<string, unknown>[]).map((g) => ({
            tipo: String(g.tipo),
            hayMas: Boolean(g.hay_mas),
            coincidencias: (
              (g.coincidencias as Record<string, unknown>[]) ?? []
            ).map((c) => ({
              tipo: String(c.tipo),
              id: String(c.id),
              titulo: String(c.titulo ?? ''),
              codigo: c.codigo == null ? null : String(c.codigo),
              contexto: (c.contexto as Record<string, unknown>) ?? {},
            })),
          })),
        );
        setAdvertencias(
          Array.isArray(cuerpo?.advertencias)
            ? (cuerpo.advertencias as unknown[]).map(String)
            : [],
        );
      } catch (e: unknown) {
        // **La lista se deja como estaba y se muestra el error.** Vaciarla
        // haría que un fallo se viera igual que «no hay coincidencias», que es
        // justo lo que el buscador no puede afirmar cuando no pudo preguntar.
        setError(mensajeDeError(e));
      } finally {
        setBuscando(false);
      }
    },
    [tenantId],
  );

  return { grupos, error, buscando, advertencias, buscar };
}
