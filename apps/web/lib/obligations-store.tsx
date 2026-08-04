'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Obligation, ObligationStatus, ObligationTask, SistemaDeclaracion } from '@ambienta/shared';
import { mockObligations } from '@/mocks/obligations';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api } from '@/lib/api-client';

const ESTADO_OBLIGACION_LABEL: Record<ObligationStatus, string> = {
  vigente: 'Vigente',
  por_vencer: 'Por vencer',
  vencida: 'Vencida',
  sin_evidencia: 'Sin evidencia',
};

interface ObligationsContextValue {
  obligations: Obligation[];
  loading: boolean;
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

function mapStatusFromApi(status: string): ObligationStatus {
  const map: Record<string, ObligationStatus> = {
    open: 'vigente',
    upcoming: 'por_vencer',
    overdue: 'vencida',
    fulfilled: 'vigente',
  };
  return map[status] ?? 'vigente';
}

function mapApiObligation(raw: Record<string, unknown>): Obligation | null {
  try {
    return {
      id: String(raw.id),
      tenantId: String(raw.tenant_id ?? ''),
      plantId: String(raw.facility_id ?? ''),
      sistema: 'RETC' as SistemaDeclaracion,
      nombre: String(raw.title ?? raw.description ?? ''),
      periodo: '',
      estado: mapStatusFromApi(String(raw.status ?? 'open')),
      proximoVencimiento: raw.due_date ? String(raw.due_date) : new Date().toISOString(),
      responsableId: raw.assigned_user_id ? String(raw.assigned_user_id) : undefined,
      tasks: [],
    };
  } catch {
    return null;
  }
}

export function ObligationsProvider({ children }: { children: ReactNode }) {
  const [obligations, setObligations] = useState<Obligation[]>(mockObligations);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    api
      .get<Record<string, unknown>[]>('/obligations/', { tenantId: user.tenantId })
      .then((data) => {
        if (cancelled) return;
        const mapped = data.map(mapApiObligation).filter((o): o is Obligation => o !== null);
        if (mapped.length > 0) setObligations(mapped);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user?.tenantId]);

  function recomputeEstado(tasks: ObligationTask[]): ObligationStatus {
    if (tasks.some((t) => t.estado === 'vencida')) return 'vencida';
    if (tasks.some((t) => t.estado === 'sin_evidencia')) return 'sin_evidencia';
    if (tasks.some((t) => t.estado === 'por_vencer')) return 'por_vencer';
    return 'vigente';
  }

  function updateTask(obligationId: string, taskId: string, updates: Partial<ObligationTask>) {
    const obligacion = obligations.find((ob) => ob.id === obligationId);
    const tareaAnterior = obligacion?.tasks.find((t) => t.id === taskId);

    setObligations((prev) =>
      prev.map((ob) => {
        if (ob.id !== obligationId) return ob;
        const tasks = ob.tasks.map((t) => (t.id === taskId ? { ...t, ...updates } : t));
        return { ...ob, tasks, estado: recomputeEstado(tasks) };
      }),
    );

    if (user?.tenantId) {
      api.patch(`/obligations/tasks/${taskId}`, updates, { tenantId: user.tenantId }).catch(() => {});
    }

    if (!obligacion || !tareaAnterior) return;

    const cambios = [];
    if (updates.estado !== undefined && updates.estado !== tareaAnterior.estado) {
      cambios.push({
        campo: 'Estado',
        antes: ESTADO_OBLIGACION_LABEL[tareaAnterior.estado],
        despues: ESTADO_OBLIGACION_LABEL[updates.estado],
      });
    }
    if (updates.evidenciaUrl !== undefined && updates.evidenciaUrl !== tareaAnterior.evidenciaUrl) {
      cambios.push({ campo: 'Evidencia', antes: tareaAnterior.evidenciaUrl ?? null, despues: updates.evidenciaUrl ?? null });
    }
    if (updates.responsableId !== undefined && updates.responsableId !== tareaAnterior.responsableId) {
      cambios.push({ campo: 'Responsable', antes: tareaAnterior.responsableId, despues: updates.responsableId });
    }
    if (updates.vencimiento !== undefined && updates.vencimiento !== tareaAnterior.vencimiento) {
      cambios.push({ campo: 'Vencimiento', antes: tareaAnterior.vencimiento, despues: updates.vencimiento });
    }
    if (cambios.length === 0) return;

    registrar({
      entidadTipo: 'tarea',
      entidadId: taskId,
      entidadLabel: `${tareaAnterior.titulo} — ${obligacion.nombre}`,
      tenantId: obligacion.tenantId,
      accion: 'actualizado',
      resumen: 'Actualizó la tarea',
      cambios,
    });
  }

  function addTask(obligationId: string, input: { titulo: string; vencimiento: string; responsableId: string }) {
    const obligacion = obligations.find((ob) => ob.id === obligationId);
    const taskId = `task-${Date.now()}`;

    setObligations((prev) =>
      prev.map((ob) => {
        if (ob.id !== obligationId) return ob;
        const newTask: ObligationTask = {
          id: taskId,
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

    if (user?.tenantId) {
      api.post(`/obligations/${obligationId}/tasks`, {
        title: input.titulo,
        due_date: input.vencimiento,
        assigned_user_id: input.responsableId,
        task_type: 'action',
      }, { tenantId: user.tenantId }).catch(() => {});
    }

    if (!obligacion) return;

    registrar({
      entidadTipo: 'tarea',
      entidadId: taskId,
      entidadLabel: `${input.titulo} — ${obligacion.nombre}`,
      tenantId: obligacion.tenantId,
      accion: 'creado',
      resumen: `Agregó la tarea a ${obligacion.nombre}`,
      cambios: [{ campo: 'Vencimiento', antes: null, despues: input.vencimiento }],
    });
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

    api.post('/obligations/', {
      title: input.nombre,
      facility_id: input.plantId,
      assigned_user_id: input.responsableId,
      due_date: input.proximoVencimiento,
      status: 'open',
    }, { tenantId: input.tenantId }).catch(() => {});

    registrar({
      entidadTipo: 'obligacion',
      entidadId: newObligation.id,
      entidadLabel: newObligation.nombre,
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: `Creó la obligación (${input.sistema})`,
      cambios: [
        { campo: 'Sistema', antes: null, despues: input.sistema },
        { campo: 'Período', antes: null, despues: input.periodo },
        { campo: 'Próximo vencimiento', antes: null, despues: input.proximoVencimiento },
      ],
    });
  }

  return (
    <ObligationsContext.Provider value={{ obligations, loading, updateTask, addTask, addObligation }}>
      {children}
    </ObligationsContext.Provider>
  );
}

export function useObligations() {
  const ctx = useContext(ObligationsContext);
  if (!ctx) throw new Error('useObligations debe usarse dentro de <ObligationsProvider>');
  return ctx;
}
