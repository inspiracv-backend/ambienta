'use client';

import { useEffect, useId, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ObligationStatus } from '@ambienta/shared';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useObligations } from '@/lib/obligations-store';
import { usePlanAccion } from '@/lib/plan-accion-store';
import type { TaskDetailModalProps } from './TaskDetailModal.types';

const ESTADOS_INCUMPLIMIENTO = new Set<ObligationStatus>(['vencida', 'sin_evidencia']);

const ESTADOS: { value: ObligationStatus; label: string }[] = [
  { value: 'vigente', label: 'Vigente' },
  { value: 'por_vencer', label: 'Por vencer' },
  { value: 'vencida', label: 'Vencida' },
  { value: 'sin_evidencia', label: 'Sin evidencia' },
];

/**
 * S-15 Detalle de Tarea/Subtarea. Integración real: mutation a apps/api +
 * evidencia real desde Google Drive/OneDrive Picker cuando exista spec aprobada.
 */
export function TaskDetailModal({ task, obligationId, obligationNombre, tenantId, responsableOptions, onOpenChange }: TaskDetailModalProps) {
  const { updateTask } = useObligations();
  const { createPlan, findByOrigen } = usePlanAccion();
  const router = useRouter();
  const formId = useId();

  const [estado, setEstado] = useState<ObligationStatus>('vigente');
  const [vencimiento, setVencimiento] = useState('');
  const [responsableId, setResponsableId] = useState('');
  const [evidenciaUrl, setEvidenciaUrl] = useState('');

  useEffect(() => {
    if (task) {
      setEstado(task.estado);
      setVencimiento(task.vencimiento.slice(0, 10));
      setResponsableId(task.responsableId);
      setEvidenciaUrl(task.evidenciaUrl ?? '');
    }
  }, [task]);

  if (!task) return null;

  const existingPlan = findByOrigen(task.id);

  function handleGenerarPlan() {
    const plan = createPlan({
      tenantId,
      origenTipo: 'tarea_obligacion',
      origenId: task!.id,
      origenLabel: `${task!.titulo} — ${obligationNombre}`,
      titulo: `Plan de acción — ${task!.titulo}`,
      responsableId: responsableId || undefined,
      fechaLimite: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    });
    onOpenChange(false);
    router.push(`/planes-accion/${plan.id}`);
  }

  function handleSave() {
    updateTask(obligationId, task!.id, {
      estado,
      vencimiento: new Date(vencimiento).toISOString(),
      responsableId,
      evidenciaUrl: evidenciaUrl.trim() || undefined,
    });
    onOpenChange(false);
  }

  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
          <div className="flex items-start justify-between">
            <Dialog.Title className="text-lg font-semibold text-slate-900">{task.titulo}</Dialog.Title>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="mt-5 flex flex-col gap-4">
            <FormField label="Estado" htmlFor={`${formId}-estado`}>
              <select
                id={`${formId}-estado`}
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                value={estado}
                onChange={(e) => setEstado(e.target.value as ObligationStatus)}
              >
                {ESTADOS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="Vencimiento" htmlFor={`${formId}-vencimiento`}>
              <Input id={`${formId}-vencimiento`} type="date" value={vencimiento} onChange={(e) => setVencimiento(e.target.value)} />
            </FormField>

            <FormField label="Responsable" htmlFor={`${formId}-responsable`}>
              <select
                id={`${formId}-responsable`}
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                value={responsableId}
                onChange={(e) => setResponsableId(e.target.value)}
              >
                <option value="">Sin asignar</option>
                {responsableOptions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.nombre}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="Evidencia (Google Drive / OneDrive)" htmlFor={`${formId}-evidencia`}>
              <Input id={`${formId}-evidencia`} placeholder="Pega el enlace de la evidencia" value={evidenciaUrl} onChange={(e) => setEvidenciaUrl(e.target.value)} />
            </FormField>

            {ESTADOS_INCUMPLIMIENTO.has(estado) && (
              existingPlan ? (
                <Button variant="secondary" type="button" onClick={() => { onOpenChange(false); router.push(`/planes-accion/${existingPlan.id}`); }}>
                  Ver Plan de Acción existente
                </Button>
              ) : (
                <Button variant="secondary" type="button" onClick={handleGenerarPlan}>
                  Generar Plan de Acción
                </Button>
              )
            )}
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="secondary">Cancelar</Button>
            </Dialog.Close>
            <Button onClick={handleSave}>Guardar</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
