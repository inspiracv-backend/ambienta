'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';
import {
  mapPipeline,
  PIPELINE_VACIO,
  type EtapaCrm,
  type Pipeline,
  type TratoCrm,
} from '@/lib/crm';

/**
 * El pipeline, pedido por la pantalla que lo usa.
 *
 * **No es un provider global** como `ObligationsProvider` y compañía. Esos
 * envuelven todo el dashboard, así que piden sus datos en cada pantalla que se
 * abra; el CRM lo mira quien vende, no quien evalúa una norma, y montarlo
 * arriba haría una petición de más en las otras veinte pantallas.
 *
 * Tampoco hay datos de ejemplo de respaldo. La lección de #208 es que un store
 * que muestra ejemplos cuando la API responde vacío no distingue "no hay nada"
 * de "no se pudo preguntar", y en un pipeline comercial eso significa enseñar
 * oportunidades que no existen.
 */
export function useCrmPipeline() {
  const { user } = useSession();
  const [pipeline, setPipeline] = useState<Pipeline>(PIPELINE_VACIO);
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
    try {
      const raw = await api.get<Record<string, unknown>>('/crm/pipeline', {
        tenantId: user.tenantId,
      });
      if (!vigente.current) return;
      setPipeline(mapPipeline(raw));
      setErrorDeCarga(null);
    } catch (e) {
      if (!vigente.current) return;
      // El pipeline se deja **vacío**, no con lo último conocido: un tablero
      // que sigue mostrando tarjetas cuando la petición falló se lee como el
      // estado actual del negocio.
      setPipeline(PIPELINE_VACIO);
      setErrorDeCarga(mensajeDeError(e));
    } finally {
      if (vigente.current) setCargando(false);
    }
  }, [user?.tenantId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  /**
   * Mueve un trato de columna y devuelve **qué más pasó**.
   *
   * La tarjeta se mueve en pantalla antes de que responda el servidor —
   * arrastrar algo y verlo volver a su sitio mientras se espera es peor que no
   * moverlo—, pero si el servidor rechaza **se devuelve al lugar original**.
   * Dejarla en la columna nueva con un mensaje de error al lado sería la peor
   * de las dos: la pantalla afirmando algo que la base no tiene.
   */
  const mover = useCallback(
    async (
      trato: TratoCrm,
      destino: EtapaCrm,
      motivo?: string,
    ): Promise<{ ok: boolean; efectos: string[]; error?: string }> => {
      if (!user?.tenantId) return { ok: false, efectos: [], error: 'Sin sesión.' };
      if (trato.etapaId === destino.id) return { ok: true, efectos: [] };

      const anterior = pipeline;
      setPipeline(moverEnLaVista(pipeline, trato, destino));

      try {
        const raw = await api.post<Record<string, unknown>>(
          `/crm/deals/${trato.id}/stage`,
          { stage_id: destino.id, motivo: motivo ?? null },
          { tenantId: user.tenantId },
        );
        const efectos = Array.isArray(raw.efectos) ? raw.efectos.map(String) : [];
        // Se recarga en vez de creerle a la vista optimista: el movimiento
        // pudo cerrar el trato, limpiar un motivo o cambiar totales de dos
        // columnas, y reconstruir todo eso a mano acá sería la misma regla
        // escrita por segunda vez.
        await cargar();
        return { ok: true, efectos };
      } catch (e) {
        if (vigente.current) setPipeline(anterior);
        return { ok: false, efectos: [], error: mensajeDeError(e) };
      }
    },
    [pipeline, user?.tenantId, cargar],
  );

  return { pipeline, cargando, errorDeCarga, mover, recargar: cargar };
}

/**
 * El movimiento en la vista, mientras el servidor responde.
 *
 * `totalTratos` se ajusta en las dos columnas porque es el número que la
 * cabecera muestra; los montos **no** se tocan: recalcularlos acá sería sumar
 * en el navegador lo que el servidor suma por moneda sobre todo lo que hay,
 * incluido lo que no vino por el tope. Vuelven correctos con la recarga.
 */
export function moverEnLaVista(
  pipeline: Pipeline,
  trato: TratoCrm,
  destino: EtapaCrm,
): Pipeline {
  return {
    ...pipeline,
    columnas: pipeline.columnas.map((col) => {
      if (col.etapa.id === trato.etapaId) {
        return {
          ...col,
          tratos: col.tratos.filter((t) => t.id !== trato.id),
          totalTratos: Math.max(0, col.totalTratos - 1),
        };
      }
      if (col.etapa.id === destino.id) {
        return {
          ...col,
          tratos: [{ ...trato, etapaId: destino.id }, ...col.tratos],
          totalTratos: col.totalTratos + 1,
        };
      }
      return col;
    }),
  };
}
