'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';

/**
 * Las tareas de un plan de acción (#169), contra `/audits/action-plans/{id}/tasks`.
 *
 * Hasta el 14-sep no existían en el modelo: la ficha mostraba una lista siempre
 * vacía y marcar una tarea se perdía al recargar. Viven en `tasks`, la misma
 * tabla que las de las obligaciones, con `action_plan_id`.
 *
 * **Se cargan en la ficha, no en el listado de planes**: pedirlas desde el
 * listado sería una petición por plan. El listado sigue con `tareas: []` y así
 * lo dice su mapper.
 */

export type EstadoDeTarea = 'todo' | 'in_progress' | 'blocked' | 'review' | 'done' | 'cancelled';

/**
 * Del vocabulario de la base a la pantalla. **Manda la base**: lo que no se
 * reconoce se muestra crudo, en vez de esconderse tras un guion o convertirse
 * en "pendiente" — un valor feo se arregla, uno escondido no.
 */
export const ESTADO_DE_TAREA: Record<string, string> = {
  todo: 'Pendiente',
  in_progress: 'En curso',
  blocked: 'Bloqueada',
  review: 'En revisión',
  done: 'Hecha',
  cancelled: 'Cancelada',
};

export function etiquetaDeEstado(estado: string): string {
  return ESTADO_DE_TAREA[estado] ?? estado;
}

export interface TareaDelPlan {
  id: string;
  titulo: string;
  estado: string;
  responsableId: string | null;
  vence: string | null;
  completadaEn: string | null;
}

export function tareaDesdeApi(raw: Record<string, unknown>): TareaDelPlan {
  return {
    id: String(raw.id),
    titulo: String(raw.title ?? ''),
    estado: String(raw.status ?? 'todo'),
    responsableId: raw.assignee_user_id ? String(raw.assignee_user_id) : null,
    vence: raw.due_at ? String(raw.due_at) : null,
    completadaEn: raw.completed_at ? String(raw.completed_at) : null,
  };
}

export function useTareasDelPlan(planId: string) {
  const { user } = useSession();
  const tenantId = user?.tenantId ?? null;
  const [tareas, setTareas] = useState<TareaDelPlan[] | null>(null);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const [errorDeEscritura, setErrorDeEscritura] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!tenantId) return;
    try {
      const filas = await api.get<Record<string, unknown>[]>(`/audits/action-plans/${planId}/tasks`, { tenantId });
      setTareas(filas.map(tareaDesdeApi));
      setErrorDeCarga(null);
    } catch (e) {
      // **Se dice que falló** (#208): una lista vacía se leería como "este plan
      // no tiene tareas".
      setErrorDeCarga(mensajeDeError(e));
    }
  }, [planId, tenantId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  /**
   * Marca o desmarca. La vista cambia de inmediato y **vuelve atrás si la base
   * lo rechaza**, diciendo por qué.
   */
  async function marcar(tarea: TareaDelPlan, hecha: boolean): Promise<void> {
    if (!tenantId) return;
    const estadoNuevo: EstadoDeTarea = hecha ? 'done' : 'todo';
    const anterior = tarea;
    setErrorDeEscritura(null);
    setTareas((prev) => prev?.map((t) => (t.id === tarea.id ? { ...t, estado: estadoNuevo } : t)) ?? prev);
    try {
      const guardada = await api.patch<Record<string, unknown>>(
        `/audits/action-plans/tasks/${tarea.id}`,
        { status: estadoNuevo },
        { tenantId },
      );
      const real = tareaDesdeApi(guardada);
      setTareas((prev) => prev?.map((t) => (t.id === real.id ? real : t)) ?? prev);
    } catch (e) {
      setTareas((prev) => prev?.map((t) => (t.id === anterior.id ? anterior : t)) ?? prev);
      setErrorDeEscritura(`No se guardó «${anterior.titulo}»: ${mensajeDeError(e)}`);
    }
  }

  /** Agrega una tarea. Rechaza si la base no la guardó; no se muestra hasta que existe. */
  async function agregar(datos: { titulo: string; responsableId: string | null; vence: string | null }): Promise<void> {
    if (!tenantId) throw new Error('La sesión no tiene empresa.');
    const creada = await api.post<Record<string, unknown>>(
      `/audits/action-plans/${planId}/tasks`,
      {
        title: datos.titulo,
        ...(datos.responsableId ? { assignee_user_id: datos.responsableId } : {}),
        // Fecha de calendario: se ancla al final del día para que no retroceda
        // uno en husos al oeste de Greenwich (`lib/fechas.ts`).
        ...(datos.vence ? { due_at: `${datos.vence}T23:59:00` } : {}),
      },
      { tenantId },
    );
    setTareas((prev) => [...(prev ?? []), tareaDesdeApi(creada)]);
  }

  return { tareas, errorDeCarga, errorDeEscritura, marcar, agregar, recargar: cargar };
}
