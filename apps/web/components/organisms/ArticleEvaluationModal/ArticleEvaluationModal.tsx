'use client';

import { useEffect, useId, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { RespuestaCumplimiento } from '@ambienta/shared';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { usePlanAccion } from '@/lib/plan-accion-store';
import type { ArticleEvaluationModalProps } from './ArticleEvaluationModal.types';

const ESTADOS: { value: RespuestaCumplimiento; label: string }[] = [
  { value: 'SI', label: 'Sí' },
  { value: 'NO', label: 'No' },
  { value: 'NA', label: 'No aplica' },
];

/**
 * S-10 Evaluar Artículo. "Forma de Cumplimiento" es obligatoria si el estado
 * es SI/NO (H5 — prevención de errores, validado antes de guardar).
 * Integración real: reemplazar por mutation a apps/api + adjuntar evidencia
 * real desde Google Drive/OneDrive Picker (RF-07) cuando exista spec aprobada.
 */
export function ArticleEvaluationModal({ articulo, normId, normNombre, tenantId, responsableOptions, onOpenChange }: ArticleEvaluationModalProps) {
  const { updateArticulo } = useLegalMatrix();
  const { createPlan, findByOrigen } = usePlanAccion();
  const router = useRouter();
  const formId = useId();

  const [estado, setEstado] = useState<RespuestaCumplimiento>('NA');
  const [formaCumplimiento, setFormaCumplimiento] = useState('');
  const [responsableId, setResponsableId] = useState('');
  const [evidenciaUrl, setEvidenciaUrl] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (articulo) {
      setEstado(articulo.respuesta === 'N_E' ? 'NA' : articulo.respuesta);
      setFormaCumplimiento(articulo.formaCumplimiento ?? '');
      setResponsableId(articulo.responsableId ?? '');
      setEvidenciaUrl(articulo.evidenciaUrl ?? '');
      setError(null);
    }
  }, [articulo]);

  if (!articulo) return null;

  const existingPlan = findByOrigen(articulo.id);

  function handleGenerarPlan() {
    const plan = createPlan({
      tenantId,
      origenTipo: 'articulo',
      origenId: articulo!.id,
      origenLabel: `${articulo!.numero} — ${normNombre}`,
      titulo: `Plan de acción — ${articulo!.numero}`,
      responsableId: responsableId || undefined,
      fechaLimite: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    });
    onOpenChange(false);
    router.push(`/planes-accion/${plan.id}`);
  }

  function handleSave() {
    if ((estado === 'SI' || estado === 'NO') && !formaCumplimiento.trim()) {
      setError('Indica la forma de cumplimiento para este estado.');
      return;
    }
    updateArticulo(normId, articulo!.id, {
      respuesta: estado,
      formaCumplimiento: formaCumplimiento.trim() || undefined,
      responsableId: responsableId || undefined,
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
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                Evaluar {articulo.numero}
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-slate-500">
                {articulo.descripcion}
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="mt-5 flex flex-col gap-4">
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-slate-700">Estado</legend>
              <div className="flex gap-2">
                {ESTADOS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setEstado(opt.value)}
                    aria-pressed={estado === opt.value}
                    className={
                      estado === opt.value
                        ? 'flex-1 rounded-lg border-2 border-brand-600 bg-brand-50 px-3 py-2 text-sm font-medium text-brand-700'
                        : 'flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50'
                    }
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </fieldset>

            <FormField
              label="Forma de cumplimiento"
              htmlFor={`${formId}-forma`}
              required={estado !== 'NA'}
              error={error ?? undefined}
              hint="Obligatorio cuando el estado es Sí o No."
            >
              <textarea
                id={`${formId}-forma`}
                rows={3}
                className="w-full rounded-lg border border-slate-300 p-3 text-sm"
                value={formaCumplimiento}
                onChange={(e) => setFormaCumplimiento(e.target.value)}
              />
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
              <Input
                id={`${formId}-evidencia`}
                placeholder="Pega el enlace de la evidencia"
                value={evidenciaUrl}
                onChange={(e) => setEvidenciaUrl(e.target.value)}
              />
            </FormField>

            {estado === 'NO' && (
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
            <Button onClick={handleSave}>Guardar evaluación</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
