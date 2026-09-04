'use client';

import { useEffect, useId, useMemo, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button, Textarea } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { necesitaMotivo, type EtapaCrm, type TratoCrm } from '@/lib/crm';
import type { Resultado } from '@/lib/crm-empresas-store';

/**
 * Mover un trato de etapa desde la ficha de la empresa.
 *
 * ## Por qué el motivo se pide antes y no después del 422
 *
 * Mover a una etapa de tipo `lost` **exige motivo**, y el servidor lo rechaza
 * sin él. Preguntarlo acá es cortesía, no la barrera: quien marca un trato como
 * perdido espera que le pregunten por qué, no que le rechacen el movimiento con
 * un error de validación. La regla vive en `services/crm.py`; `necesitaMotivo`
 * solo la consulta para saber cuándo mostrar el campo.
 *
 * ## Y se dice qué más pasó
 *
 * La respuesta trae `efectos`: mover puede cerrar el trato o reabrirlo y
 * limpiar su cierre. Sin mostrarlos, la persona lo descubre cuando el trato
 * desaparece de sus pendientes.
 */
export function MoverTratoModal({
  open,
  onOpenChange,
  trato,
  etapas,
  onMover,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trato: TratoCrm | null;
  etapas: EtapaCrm[];
  onMover: (tratoId: string, etapaId: string, motivo?: string) => Promise<Resultado>;
}) {
  const formId = useId();
  const [etapaId, setEtapaId] = useState('');
  const [motivo, setMotivo] = useState('');
  const [moviendo, setMoviendo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setEtapaId(trato?.etapaId ?? '');
    setMotivo('');
    setError(null);
  }, [open, trato]);

  const destino = useMemo(
    () => etapas.find((e) => e.id === etapaId) ?? null,
    [etapas, etapaId],
  );
  const pideMotivo = destino !== null && necesitaMotivo(destino);
  const cambia = trato !== null && etapaId !== '' && etapaId !== trato.etapaId;
  const puedeMover =
    cambia && !moviendo && (!pideMotivo || motivo.trim().length > 0);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!puedeMover || !trato) return;
    setMoviendo(true);
    setError(null);

    const r = await onMover(trato.id, etapaId, pideMotivo ? motivo : undefined);

    setMoviendo(false);
    if (r.ok) {
      onOpenChange(false);
      return;
    }
    setError(r.error ?? 'No se pudo mover el trato.');
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full max-w-md -translate-x-1/2 -translate-y-1/2 flex-col rounded-card bg-white shadow-lg">
          <div className="flex items-start justify-between border-b border-slate-200 p-6">
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                Mover oportunidad
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-slate-500">
                {trato ? trato.titulo : ''}
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={enviar} className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
              <FormField label="Etapa" htmlFor={`${formId}-etapa`}>
                <select
                  id={`${formId}-etapa`}
                  value={etapaId}
                  onChange={(e) => setEtapaId(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  {etapas.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.nombre}
                    </option>
                  ))}
                </select>
              </FormField>

              {pideMotivo && (
                <FormField
                  label="Motivo de la pérdida"
                  htmlFor={`${formId}-motivo`}
                  required
                  hint="Aprender por qué se pierde es la razón de tener un pipeline."
                >
                  <Textarea
                    id={`${formId}-motivo`}
                    rows={3}
                    value={motivo}
                    onChange={(e) => setMotivo(e.target.value)}
                    placeholder="Precio, plazo, se fue con la competencia…"
                  />
                </FormField>
              )}

              {destino?.tipo === 'won' && (
                <p className="rounded-lg border border-semaforo-cumple/30 bg-semaforo-cumple-bg px-3 py-2 text-xs text-slate-700">
                  Al ganar, el trato queda cerrado. Después se puede promover a un
                  contrato desde esta misma ficha.
                </p>
              )}

              {error && (
                <p
                  role="alert"
                  className="rounded-lg border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple"
                >
                  {error}
                </p>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-200 p-4">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">
                  Cancelar
                </Button>
              </Dialog.Close>
              <Button type="submit" disabled={!puedeMover}>
                {moviendo ? 'Moviendo…' : 'Mover'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
