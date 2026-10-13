'use client';

import { useCallback } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';

/**
 * Anotar en el servidor que se emitió un documento (RNF-26, decisión 9 del
 * 21-sep): `POST /emisiones/`.
 *
 * Hasta ese día se anotaba en el historial **de la sesión del navegador**, que
 * se vacía al recargar: el servidor no sabía que alguien se había llevado una
 * copia de los datos de la empresa.
 *
 * **No bloquea el documento.** Si la anotación falla, el PDF o el CSV salen
 * igual —detener una exportación porque el registro no respondió sería peor—,
 * pero se avisa: que falte el rastro no puede pasar en silencio.
 */
export interface Emision {
  documento: 'informe_de_auditoria' | 'matriz_de_aspectos' | 'reporte';
  titulo: string;
  formato: 'pdf' | 'csv';
  filas?: number;
  filtros?: string[];
  /** El registro al que pertenece, si hay uno: así aparece en su historial. */
  entidadTipo?: 'audits';
  entidadId?: string;
}

export function useAnotarEmision() {
  const { user } = useSession();
  const { mostrarToast } = useToast();
  const tenantId = user?.tenantId ?? null;

  return useCallback(
    (e: Emision) => {
      if (!tenantId) return;
      api
        .post(
          '/emisiones/',
          {
            documento: e.documento,
            titulo: e.titulo.slice(0, 300),
            formato: e.formato,
            filas: e.filas ?? null,
            filtros: e.filtros ?? [],
            entidad_tipo: e.entidadTipo ?? null,
            entidad_id: e.entidadId ?? null,
          },
          { tenantId },
        )
        .catch((error: unknown) => {
          mostrarToast({
            tipo: 'error',
            mensaje: 'No se pudo anotar la emisión en el registro',
            descripcion: mensajeDeError(error),
          });
        });
    },
    [tenantId, mostrarToast],
  );
}
