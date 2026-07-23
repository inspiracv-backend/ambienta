'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { OrigenPlanAccion, PlanAccion } from '@ambienta/shared';
import { mockActionPlans } from '@/mocks/action-plans';

interface PlanAccionContextValue {
  plans: PlanAccion[];
  createPlan: (input: {
    tenantId: string;
    origenTipo: OrigenPlanAccion;
    origenId: string;
    origenLabel: string;
    titulo: string;
    responsableId?: string;
    fechaLimite: string;
  }) => PlanAccion;
  toggleTarea: (planId: string, tareaId: string) => void;
  findByOrigen: (origenId: string) => PlanAccion | undefined;
}

const PlanAccionContext = createContext<PlanAccionContextValue | null>(null);

/**
 * Estado en memoria para esta iteración (mismo patrón que los demás stores).
 * Integración real: mutations vía apps/api cuando exista spec aprobada para
 * Planes de Acción (RF-19).
 */
export function PlanAccionProvider({ children }: { children: ReactNode }) {
  const [plans, setPlans] = useState<PlanAccion[]>(mockActionPlans);

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
    return newPlan;
  }

  function toggleTarea(planId: string, tareaId: string) {
    setPlans((prev) =>
      prev.map((plan) => {
        if (plan.id !== planId) return plan;
        const tareas = plan.tareas.map((t) => (t.id === tareaId ? { ...t, hecha: !t.hecha } : t));
        const estado = tareas.length > 0 && tareas.every((t) => t.hecha) ? 'cerrado' : plan.estado === 'abierto' ? 'en_progreso' : plan.estado;
        return { ...plan, tareas, estado };
      }),
    );
  }

  function findByOrigen(origenId: string) {
    return plans.find((p) => p.origenId === origenId);
  }

  return (
    <PlanAccionContext.Provider value={{ plans, createPlan, toggleTarea, findByOrigen }}>
      {children}
    </PlanAccionContext.Provider>
  );
}

export function usePlanAccion() {
  const ctx = useContext(PlanAccionContext);
  if (!ctx) throw new Error('usePlanAccion debe usarse dentro de <PlanAccionProvider>');
  return ctx;
}
