'use client';

import { useEffect, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

/** Un intento de presentar una declaración, con su propio folio. */
export interface Presentacion {
  id: string;
  versionNo: number;
  estado: string;
  folio: string | null;
  periodo: string | null;
  presentadaEl: string | null;
  presentadaPor: string | null;
  revisadaPor: string | null;
  motivoRechazo: string | null;
}

export interface HistorialDePresentaciones {
  /**
   * `null` mientras no se sabe. **No es lo mismo que una lista vacía**: la
   * primera es una pregunta sin responder y la segunda una respuesta.
   *
   * Este proyecto dibujó un cero sobre algo que nadie midió cuatro veces. Acá
   * el daño sería particular: un historial vacío por una consulta que no volvió
   * se lee como "esta declaración nunca se presentó", que en un sistema de
   * cumplimiento es la afirmación más grave que la pantalla puede hacer.
   */
  presentaciones: Presentacion[] | null;
  error: string | null;
}

/**
 * El historial de presentaciones de una declaración.
 *
 * Se vuelve a pedir cuando cambia `revalidarCon`, que quien lo use debe atar al
 * estado de la declaración: presentar, aceptar o rechazar agregan o cierran una
 * fila, y sin eso la pantalla mostraría el historial de antes de la acción que
 * el usuario acaba de hacer.
 */
export function usarPresentaciones(
  obligationId: string,
  revalidarCon: string,
): HistorialDePresentaciones {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [presentaciones, setPresentaciones] = useState<Presentacion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Sin tenant se sale **sin borrar** lo que ya se sabía. La sesión pasa por
    // `null` mientras se resuelve, y limpiar acá haría que el historial se
    // llenara y se vaciara solo — el defecto que ya apareció en `iso-store`.
    if (!tenantId || !obligationId) return;
    let vigente = true;

    api
      .get<Record<string, unknown>[]>(
        `/obligations/${obligationId}/presentaciones`,
        { tenantId },
      )
      .then((filas) => {
        if (!vigente) return;
        setError(null);
        setPresentaciones(
          (Array.isArray(filas) ? filas : []).map((f) => ({
            id: String(f.id),
            versionNo: Number(f.version_no ?? 0),
            estado: String(f.status ?? ''),
            folio: f.external_folio == null ? null : String(f.external_folio),
            periodo: f.period_label == null ? null : String(f.period_label),
            presentadaEl: f.submitted_at == null ? null : String(f.submitted_at),
            presentadaPor: f.submitted_by == null ? null : String(f.submitted_by),
            revisadaPor: f.reviewed_by == null ? null : String(f.reviewed_by),
            motivoRechazo:
              (f.submission_data as Record<string, unknown> | null)?.motivo_rechazo == null
                ? null
                : String((f.submission_data as Record<string, unknown>).motivo_rechazo),
          })),
        );
      })
      .catch((e: unknown) => {
        if (!vigente) return;
        // **Se dice que falló en vez de mostrar una lista vacía.** Un historial
        // vacío afirma que nunca se presentó; "no se pudo consultar" no afirma
        // nada, que es lo correcto cuando no se sabe.
        setError(mensajeDeError(e));
        setPresentaciones([]);
      });

    return () => {
      vigente = false;
    };
  }, [obligationId, tenantId, revalidarCon]);

  return { presentaciones, error };
}
