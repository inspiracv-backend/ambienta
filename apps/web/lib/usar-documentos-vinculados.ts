'use client';

import { useEffect, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

/** Un documento que respalda un registro (RF-108). */
export interface DocumentoVinculado {
  id: string;
  codigo: string | null;
  titulo: string;
  tipo: string;
  estado: string;
}

export interface RespaldoDocumental {
  /**
   * `null` mientras no se sabe. **No es lo mismo que una lista vacía.**
   *
   * Acá la distinción decide qué se le dice a un fiscalizador: una lista vacía
   * afirma «este requisito no tiene evidencia», y una consulta que no volvió no
   * afirma nada. Este proyecto dibujó un cero sobre algo que nadie midió cuatro
   * veces antes de aprenderlo.
   */
  documentos: DocumentoVinculado[] | null;
  error: string | null;
}

/**
 * Los documentos que respaldan un registro.
 *
 * Una sola ruta para las trece entidades vinculables: `entity_type` dice cuál.
 * Ver `services/vinculos_de_documentos.py` — la misma lista que valida el
 * anclaje es la que documenta qué se puede pasar acá.
 */
export function usarDocumentosVinculados(
  entityType: string,
  entityId: string,
): RespaldoDocumental {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [documentos, setDocumentos] = useState<DocumentoVinculado[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Sin tenant se sale **sin borrar** lo que ya se sabía: la sesión pasa por
    // `null` mientras se resuelve, y limpiar acá hace que el panel se llene y
    // se vacíe solo. Es el defecto que ya apareció en `iso-store`.
    if (!tenantId || !entityId) return;
    let vigente = true;

    // `encodeURIComponent` y no interpolación cruda: `entityId` viene de la
    // ruta del navegador, así que es dato de fuera.
    const consulta = new URLSearchParams({
      entity_type: entityType,
      entity_id: entityId,
    });

    api
      .get<Record<string, unknown>[]>(`/documents/vinculados?${consulta}`, {
        tenantId,
      })
      .then((filas) => {
        if (!vigente) return;
        setError(null);
        setDocumentos(
          (Array.isArray(filas) ? filas : []).map((f) => ({
            id: String(f.id),
            codigo: f.code == null ? null : String(f.code),
            titulo: String(f.title ?? ''),
            tipo: String(f.document_type ?? ''),
            estado: String(f.status ?? ''),
          })),
        );
      })
      .catch((e: unknown) => {
        if (!vigente) return;
        // Se dice que falló en vez de mostrar una lista vacía: «no se pudo
        // consultar» no afirma nada, que es lo correcto cuando no se sabe.
        setError(mensajeDeError(e));
        setDocumentos([]);
      });

    return () => {
      vigente = false;
    };
  }, [entityType, entityId, tenantId]);

  return { documentos, error };
}
