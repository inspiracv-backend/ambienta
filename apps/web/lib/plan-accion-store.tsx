'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { OrigenPlanAccion, PlanAccion } from '@ambienta/shared';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api, mensajeDeError } from '@/lib/api-client';

interface PlanAccionContextValue {
  plans: PlanAccion[];
  loading: boolean;
  /**
   * Por que la lista esta vacia, si es que fallo (#208).
   *
   * `null` = se pregunto y esto es lo que hay. Un texto = **no se pudo
   * preguntar**, y la pantalla tiene que decirlo: sin esto un fallo de red se
   * ve igual que "esta empresa no tiene ninguno".
   */
  errorDeCarga: string | null;
  createPlan: (input: {
    tenantId: string;
    origenTipo: OrigenPlanAccion;
    origenId: string;
    origenLabel: string;
    titulo: string;
    responsableId?: string;
    fechaLimite: string;
  }) => PlanAccion;
  findByOrigen: (origenId: string) => PlanAccion | undefined;
}

const PlanAccionContext = createContext<PlanAccionContextValue | null>(null);

export function PlanAccionProvider({ children }: { children: ReactNode }) {
  const [plans, setPlans] = useState<PlanAccion[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    api
      .get<Record<string, unknown>[]>('/audits/action-plans/', { tenantId: user.tenantId })
      .then((data) => {
        if (cancelled) return;
        const mapped: PlanAccion[] = data.map((raw) => ({
          id: String(raw.id),
          tenantId: String(raw.tenant_id ?? ''),
          origenTipo: 'no_conformidad' as OrigenPlanAccion,
          origenId: String(raw.nonconformity_id ?? ''),
          origenLabel: String(raw.objective ?? ''),
          titulo: String(raw.objective ?? raw.root_cause ?? ''),
          responsableId: raw.owner_user_id ? String(raw.owner_user_id) : undefined,
          fechaLimite: raw.target_date ? String(raw.target_date) : new Date().toISOString(),
          estado: (raw.status === 'closed' ? 'cerrado' : raw.status === 'in_progress' ? 'en_progreso' : 'abierto') as PlanAccion['estado'],
          // El listado no trae tareas: se cargan en la ficha del plan
          // (`lib/tareas-del-plan.ts`), para no pedir una lista por cada plan.
          tareas: [],
        }));
        // **Se escribe siempre, incluso vacio** (#208). El `if (length > 0)`
        // de antes no distinguia dos cosas muy distintas: que la API fallara
        // —donde quedarse con lo que hay es un respaldo razonable— y que
        // respondiera **cero filas**, donde quedarse con los datos de ejemplo
        // es mostrar algo que no existe.
        //
        // El `catch` sigue conservando lo ultimo conocido, asi que trabajar sin
        // backend levantado sigue funcionando: ahi la peticion falla, no
        // devuelve vacio.
        setPlans(mapped);
      })
      .catch((e: unknown) => {
        // **Se dice que fallo.** Con la lista vacia y sin mensaje, la
        // pantalla afirma 'no hay nada' cuando la verdad es 'no se pudo
        // preguntar' — que es la misma mentira de #208 en su otra forma.
        setErrorDeCarga(mensajeDeError(e));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user?.tenantId]);

  function createPlan(input: {
    tenantId: string;
    origenTipo: OrigenPlanAccion;
    origenId: string;
    origenLabel: string;
    titulo: string;
    responsableId?: string;
    fechaLimite: string;
  }): PlanAccion {
    const newPlan: PlanAccion = {
      id: `plan-${Date.now()}`,
      tenantId: input.tenantId,
      origenTipo: input.origenTipo,
      origenId: input.origenId,
      origenLabel: input.origenLabel,
      titulo: input.titulo,
      responsableId: input.responsableId,
      fechaLimite: input.fechaLimite,
      estado: 'abierto',
      tareas: [],
    };
    setPlans((prev) => [...prev, newPlan]);

    api.post('/audits/action-plans/', {
      objective: input.titulo,
      owner_user_id: input.responsableId,
      target_date: input.fechaLimite,
      status: 'draft',
    }, { tenantId: input.tenantId }).catch(() => {});

    registrar({
      entidadTipo: 'plan_accion',
      entidadId: newPlan.id,
      entidadLabel: newPlan.titulo,
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: 'Generó el plan de acción',
      cambios: [
        { campo: 'Origen', antes: null, despues: input.origenLabel },
        { campo: 'Fecha límite', antes: null, despues: input.fechaLimite },
      ],
    });

    return newPlan;
  }

  // `toggleTarea` se quitó el 13-sep: las tareas de un plan no existen en el
  // modelo (#169), el mapper las arma siempre vacías, y marcar una se perdía
  // al recargar — y además podía mostrar el plan como cerrado sin que la base
  // lo supiera. Vuelve con el modelo de tareas.

  function findByOrigen(origenId: string) {
    return plans.find((p) => p.origenId === origenId);
  }

  return (
    <PlanAccionContext.Provider value={{ plans, loading, errorDeCarga, createPlan, findByOrigen }}>
      {children}
    </PlanAccionContext.Provider>
  );
}

export function usePlanAccion() {
  const ctx = useContext(PlanAccionContext);
  if (!ctx) throw new Error('usePlanAccion debe usarse dentro de <PlanAccionProvider>');
  return ctx;
}
