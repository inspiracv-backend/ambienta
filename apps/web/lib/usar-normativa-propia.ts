'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

/** Una norma cargada por la propia empresa: su RCA o una ISO interna (RF-10). */
export interface NormaPropia {
  id: string;
  normType: string;
  normNumber: string | null;
  title: string;
  organismo: string | null;
  publicadaEl: string | null;
  /** Cuántos considerandos tiene cargados. **Derivado, no guardado.** */
  articulos: number;
}

export interface NormativaPropia {
  /**
   * `null` mientras no se sabe. **No es una lista vacía.**
   *
   * Acá la distinción decide si la pantalla afirma «esta empresa no cargó su
   * RCA» — que en un sistema de cumplimiento es una acusación de que falta un
   * permiso, no un dato neutro.
   */
  normas: NormaPropia[] | null;
  error: string | null;
  guardando: boolean;
  errorAlGuardar: string | null;
  registrar: (datos: Record<string, unknown>) => Promise<boolean>;
}

function mapear(f: Record<string, unknown>): NormaPropia {
  return {
    id: String(f.id),
    normType: String(f.norm_type ?? ''),
    normNumber: f.norm_number == null ? null : String(f.norm_number),
    title: String(f.title ?? ''),
    organismo: f.issuing_body == null ? null : String(f.issuing_body),
    publicadaEl: f.publication_date == null ? null : String(f.publication_date),
    articulos: Number(f.articulos ?? 0),
  };
}

/** La normativa propia de la empresa (RF-10, RF-11). */
export function useNormativaPropia(): NormativaPropia {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [normas, setNormas] = useState<NormaPropia[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [errorAlGuardar, setErrorAlGuardar] = useState<string | null>(null);
  const [recargas, setRecargas] = useState(0);

  useEffect(() => {
    // Sin tenant se sale **sin borrar** lo que ya se sabía: la sesión pasa por
    // `null` mientras se resuelve.
    if (!tenantId) return;
    let vigente = true;

    api
      .get<Record<string, unknown>[]>('/compliance/normativa-propia/', { tenantId })
      .then((filas) => {
        if (!vigente) return;
        setError(null);
        setNormas((Array.isArray(filas) ? filas : []).map(mapear));
      })
      .catch((e: unknown) => {
        if (!vigente) return;
        setError(mensajeDeError(e));
        setNormas([]);
      });

    return () => {
      vigente = false;
    };
  }, [tenantId, recargas]);

  const registrar = useCallback(
    async (datos: Record<string, unknown>) => {
      if (!tenantId) return false;
      setGuardando(true);
      setErrorAlGuardar(null);
      try {
        await api.post('/compliance/normativa-propia/', datos, { tenantId });
        setRecargas((n) => n + 1);
        return true;
      } catch (e: unknown) {
        // **Lo escrito se queda**: quien acaba de tipear el número de su RCA no
        // tiene por qué volver a buscarlo porque el servidor respondió mal.
        setErrorAlGuardar(mensajeDeError(e));
        return false;
      } finally {
        setGuardando(false);
      }
    },
    [tenantId],
  );

  return { normas, error, guardando, errorAlGuardar, registrar };
}
