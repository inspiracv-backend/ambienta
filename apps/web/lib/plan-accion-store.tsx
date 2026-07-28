'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { OrigenPlanAccion, PlanAccion } from '@ambienta/shared';
import { mockActionPlans } from '@/mocks/action-plans';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';

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
  const registrar = useRegistrarAuditoria();

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

    registrar({
      entidadTipo: 'plan_accion',
      entidadId: newPlan.id,
      entidadLabel: newPlan.titulo,
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: 'Generó el plan de acción',
      cambios: [
        // El origen es lo que conecta el plan con el incumplimiento que lo
        // motivó (RF-30, RF-53): sin él, en una auditoría el plan queda huérfano.
        { campo: 'Origen', antes: null, despues: input.origenLabel },
        { campo: 'Fecha límite', antes: null, despues: input.fechaLimite },
      ],
    });

    return newPlan;
  }

  function toggleTarea(planId: string, tareaId: string) {
    const plan = plans.find((p) => p.id === planId);
    const tarea = plan?.tareas.find((t) => t.id === tareaId);

    let estadoNuevo: PlanAccion['estado'] | null = null;

    setPlans((prev) =>
      prev.map((p) => {
        if (p.id !== planId) return p;
        const tareas = p.tareas.map((t) => (t.id === tareaId ? { ...t, hecha: !t.hecha } : t));
        const estado =
          tareas.length > 0 && tareas.every((t) => t.hecha) ? 'cerrado' : p.estado === 'abierto' ? 'en_progreso' : p.estado;
        estadoNuevo = estado;
        return { ...p, tareas, estado };
      }),
    );

    if (!plan || !tarea) return;

    const hechaAhora = !tarea.hecha;
    const cerroElPlan = estadoNuevo === 'cerrado' && plan.estado !== 'cerrado';

    registrar({
      entidadTipo: 'plan_accion',
      entidadId: planId,
      entidadLabel: plan.titulo,
      tenantId: plan.tenantId,
      accion: cerroElPlan ? 'cerrado' : 'actualizado',
      resumen: cerroElPlan
        ? 'Completó la última tarea y cerró el plan'
        : `${hechaAhora ? 'Completó' : 'Reabrió'} la tarea "${tarea.titulo}"`,
      cambios: [
        { campo: tarea.titulo, antes: tarea.hecha ? 'Hecha' : 'Pendiente', despues: hechaAhora ? 'Hecha' : 'Pendiente' },
        ...(cerroElPlan ? [{ campo: 'Estado del plan', antes: 'En progreso', despues: 'Cerrado' }] : []),
      ],
    });
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
