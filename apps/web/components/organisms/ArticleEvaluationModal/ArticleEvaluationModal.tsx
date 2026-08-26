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

/**
 * Los tres estados, cada uno con la pregunta que responde.
 *
 * "Sí / No / No aplica" a secas no dice **sí a qué**, y la diferencia entre
 * "No" y "No aplica" es justo la que no conviene que alguien adivine: uno es un
 * incumplimiento que hay que resolver y el otro es que el artículo no rige para
 * esta empresa. Elegir mal el segundo saca el artículo del cálculo y deja un
 * porcentaje mejor del que corresponde.
 */
const ESTADOS: { value: RespuestaCumplimiento; label: string; ayuda: string }[] = [
  { value: 'SI', label: 'Sí cumplimos', ayuda: 'Entra al cálculo como cumplido' },
  { value: 'NO', label: 'No cumplimos', ayuda: 'Entra al cálculo como incumplido' },
  { value: 'NA', label: 'No aplica', ayuda: 'No rige para esta empresa · queda fuera del cálculo' },
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
        {/* `max-w-2xl` y no `max-w-md`. El ancho de antes venia de cuando la
            descripcion era una frase sembrada; con el texto real de la BCN
            —1.400 caracteres en el articulo 3o del DS 13— el dialogo quedaba
            angosto y altisimo, con el texto legal empujando el formulario
            fuera de la pantalla. El `max-h` con scroll es la otra mitad: sin
            el, en un portatil los botones Guardar y Cancelar quedaban abajo
            del borde y no habia forma de llegar a ellos. */}
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-card bg-white shadow-lg">
          <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-6 pb-4">
            <div className="min-w-0">
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                Evaluar {articulo.numero}
              </Dialog.Title>
              <p className="mt-0.5 truncate text-xs text-slate-500">{normNombre}</p>
            </div>
            <Dialog.Close aria-label="Cerrar" className="shrink-0 text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            {/* El texto legal, en su propia caja y con su propio scroll: es
                material de consulta mientras se responde, no el encabezado del
                dialogo. Antes empujaba el formulario hacia abajo. */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Texto del artículo</p>
              <Dialog.Description className="mt-2 max-h-40 overflow-y-auto whitespace-pre-line text-sm leading-relaxed text-slate-700">
                {articulo.descripcion}
              </Dialog.Description>
            </div>

            <div className="mt-5 flex flex-col gap-4">
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-slate-700">Estado</legend>
              <div className="grid grid-cols-3 gap-2">
                {ESTADOS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setEstado(opt.value)}
                    aria-pressed={estado === opt.value}
                    className={
                      estado === opt.value
                        ? 'rounded-lg border-2 border-brand-600 bg-brand-50 px-3 py-2.5 text-left'
                        : 'rounded-lg border border-slate-300 px-3 py-2.5 text-left hover:border-slate-400 hover:bg-slate-50'
                    }
                  >
                    <span className={estado === opt.value ? 'block text-sm font-semibold text-brand-700' : 'block text-sm font-medium text-slate-700'}>
                      {opt.label}
                    </span>
                    <span className="mt-0.5 block text-xs leading-snug text-slate-500">{opt.ayuda}</span>
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
          </div>

          {/* El pie queda fijo fuera del area con scroll: los dos botones que
              cierran el dialogo tienen que estar siempre a la vista. */}
          <div className="flex justify-end gap-2 border-t border-slate-200 p-6 pt-4">
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
