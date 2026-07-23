'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Obligation, ObligationStatus, ObligationTask, SistemaDeclaracion } from '@ambienta/shared';
import { mockObligations } from '@/mocks/obligations';

interface ObligationsContextValue {
  obligations: Obligation[];
  updateTask: (obligationId: string, taskId: string, updates: Partial<ObligationTask>) => void;
  addTask: (obligationId: string, input: { titulo: string; vencimiento: string; responsableId: string }) => void;
  addObligation: (input: {
    nombre: string;
    sistema: SistemaDeclaracion;
    periodo: string;
    tenantId: string;
    plantId: string;
    responsableId: string;
    proximoVencimiento: string;
  }) => void;
}

const ObligationsContext = createContext<ObligationsContextValue | null>(null);

/**
 * Estado en memoria para esta iteración (mismo patrón que
 * LegalMatrixProvider/SessionProvider). Integración real: mutations vía
 * apps/api cuando exista spec aprobada para Obligaciones (RF-14 a RF-21).
 */
export function ObligationsProvider({ children }: { children: ReactNode }) {
  const [obligations, setObligations] = useState<Obligation[]>(mockObligations);

  function recomputeEstado(tasks: ObligationTask[]): ObligationStatus {
    if (tasks.some((t) => t.estado === 'vencida')) return 'vencida';
    if (tasks.some((t) => t.estado === 'sin_evidencia')) return 'sin_evidencia';
    if (tasks.some((t) => t.estado === 'por_vencer')) return 'por_vencer';
    return 'vigente';
  }

  function updateTask(obligationId: string, taskId: string, updates: Partial<ObligationTask>) {
    setObligations((prev) =>
      prev.map((ob) => {
        if (ob.id !== obligationId) return ob;
        const tasks = ob.tasks.map((t) => (t.id === taskId ? { ...t, ...updates } : t));
        return { ...ob, tasks, estado: recomputeEstado(tasks) };
      }),
    );
  }

  function addTask(obligationId: string, input: { titulo: string; vencimiento: string; responsableId: string }) {
    setObligations((prev) =>
      prev.map((ob) => {
        if (ob.id !== obligationId) return ob;
        const newTask: ObligationTask = {
          id: `task-${Date.now()}`,
          obligationId,
          titulo: input.titulo,
          vencimiento: input.vencimiento,
          responsableId: input.responsableId,
          estado: 'vigente',
        };
        const tasks = [...ob.tasks, newTask];
        return { ...ob, tasks, estado: recomputeEstado(tasks) };
      }),
    );
  }

  function addObligation(input: {
    nombre: string;
    sistema: SistemaDeclaracion;
    periodo: string;
    tenantId: string;
    plantId: string;
    responsableId: string;
    proximoVencimiento: string;
  }) {
    const newObligation: Obligation = {
      id: `obl-${Date.now()}`,
      tenantId: input.tenantId,
      plantId: input.plantId,
      sistema: input.sistema,
      nombre: input.nombre,
      periodo: input.periodo,
      estado: 'vigente',
      proximoVencimiento: input.proximoVencimiento,
      responsableId: input.responsableId,
      tasks: [],
    };
    setObligations((prev) => [...prev, newObligation]);
  }

  return (
    <ObligationsContext.Provider value={{ obligations, updateTask, addTask, addObligation }}>
      {children}
    </ObligationsContext.Provider>
  );
}

export function useObligations() {
  const ctx = useContext(ObligationsContext);
  if (!ctx) throw new Error('useObligations debe usarse dentro de <ObligationsProvider>');
  return ctx;
}
