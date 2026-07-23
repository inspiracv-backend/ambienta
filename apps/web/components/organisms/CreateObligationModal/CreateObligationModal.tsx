'use client';

import { useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { SistemaDeclaracion } from '@ambienta/shared';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useObligations } from '@/lib/obligations-store';
import { mockUsers } from '@/mocks/users';
import type { CreateObligationModalProps } from './CreateObligationModal.types';

const SISTEMAS: SistemaDeclaracion[] = ['RETC', 'Ley REP', 'SINADER', 'SIDREP', 'DAE'];

/**
 * Acción "Crear obligación" de S-13 — puede nacer de la Matriz Legal o de
 * forma libre (RF-14, relación bidireccional). En esta iteración solo se
 * implementa la creación libre; el origen desde un artículo de Matriz Legal
 * queda documentado como gap en seccion-e-obligaciones.md.
 */
export function CreateObligationModal({ open, onOpenChange, plants }: CreateObligationModalProps) {
  const { addObligation } = useObligations();
  const formId = useId();

  const [nombre, setNombre] = useState('');
  const [sistema, setSistema] = useState<SistemaDeclaracion>('RETC');
  const [periodo, setPeriodo] = useState('');
  const [plantId, setPlantId] = useState(plants[0]?.id ?? '');
  const [responsableId, setResponsableId] = useState('');
  const [vencimiento, setVencimiento] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const tenantId = plants[0]?.tenantId ?? '';
  const responsableOptions = mockUsers.filter((u) => u.tenantId === tenantId);
  const today = new Date().toISOString().slice(0, 10);

  function resetForm() {
    setNombre('');
    setSistema('RETC');
    setPeriodo('');
    setPlantId(plants[0]?.id ?? '');
    setResponsableId('');
    setVencimiento('');
    setErrors({});
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!nombre.trim()) next.nombre = 'Ingresa un nombre para la obligación.';
    if (!periodo.trim()) next.periodo = 'Indica el período (ej. 2026-Q3).';
    if (!vencimiento) next.vencimiento = 'Selecciona la fecha de vencimiento.';
    else if (vencimiento < today) next.vencimiento = 'La fecha no puede ser anterior a hoy.';
    if (!plantId) next.plantId = 'Selecciona una planta.';
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    addObligation({
      nombre: nombre.trim(),
      sistema,
      periodo: periodo.trim(),
      tenantId,
      plantId,
      responsableId,
      proximoVencimiento: new Date(vencimiento).toISOString(),
    });
    resetForm();
    onOpenChange(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={(next) => { onOpenChange(next); if (!next) resetForm(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
          <div className="flex items-start justify-between">
            <Dialog.Title className="text-lg font-semibold text-slate-900">Crear obligación</Dialog.Title>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4" noValidate>
            <FormField label="Nombre" htmlFor={`${formId}-nombre`} required error={errors.nombre}>
              <Input id={`${formId}-nombre`} value={nombre} invalid={!!errors.nombre} onChange={(e) => setNombre(e.target.value)} />
            </FormField>

            <div className="grid grid-cols-2 gap-3">
              <FormField label="Sistema" htmlFor={`${formId}-sistema`}>
                <select
                  id={`${formId}-sistema`}
                  className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  value={sistema}
                  onChange={(e) => setSistema(e.target.value as SistemaDeclaracion)}
                >
                  {SISTEMAS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField label="Período" htmlFor={`${formId}-periodo`} required error={errors.periodo}>
                <Input id={`${formId}-periodo`} placeholder="2026-Q3" value={periodo} invalid={!!errors.periodo} onChange={(e) => setPeriodo(e.target.value)} />
              </FormField>
            </div>

            <FormField label="Planta" htmlFor={`${formId}-planta`} required error={errors.plantId}>
              <select
                id={`${formId}-planta`}
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                value={plantId}
                onChange={(e) => setPlantId(e.target.value)}
              >
                {plants.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="Responsable" htmlFor={`${formId}-responsable`}>
              <select
                id={`${formId}-responsable`}
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                value={responsableId}
                onChange={(e) => setResponsableId(e.target.value)}
              >
                <option value="">Sin asignar</option>
                {responsableOptions.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nombre}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="Próximo vencimiento" htmlFor={`${formId}-vencimiento`} required error={errors.vencimiento}>
              <Input id={`${formId}-vencimiento`} type="date" min={today} value={vencimiento} invalid={!!errors.vencimiento} onChange={(e) => setVencimiento(e.target.value)} />
            </FormField>

            <div className="mt-2 flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">Cancelar</Button>
              </Dialog.Close>
              <Button type="submit">Crear</Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
