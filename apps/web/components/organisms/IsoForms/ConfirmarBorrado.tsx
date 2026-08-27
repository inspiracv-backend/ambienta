'use client';

import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/atoms';
import type { ConfirmarBorradoProps } from './IsoForms.types';

/**
 * Confirmación antes de borrar.
 *
 * ## Por qué se nombra lo que se borra
 *
 * "¿Confirmas eliminar?" no dice cuál. En una tabla de treinta filas, quien
 * abrió el diálogo desde la fila equivocada no tiene forma de darse cuenta. El
 * nombre del registro va en el texto, no en el título genérico.
 *
 * ## Y por qué el botón dice "Eliminar" y no "Aceptar"
 *
 * El botón tiene que decir qué hace. "Aceptar" al lado de "Cancelar" obliga a
 * leer el párrafo para saber cuál es cuál, y la gente no lo lee — pulsa el de
 * la derecha.
 */
export function ConfirmarBorrado({
  open,
  onOpenChange,
  queSeBorra,
  advertencia,
  onConfirmar,
}: ConfirmarBorradoProps) {
  const [borrando, setBorrando] = useState(false);

  async function confirmar() {
    setBorrando(true);
    const ok = await onConfirmar();
    setBorrando(false);
    if (ok) onOpenChange(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
          <div className="flex gap-3">
            <AlertTriangle
              className="mt-0.5 h-5 w-5 shrink-0 text-semaforo-no-cumple"
              aria-hidden
            />
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                ¿Eliminar este registro?
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-slate-600">
                Se va a eliminar <strong className="text-slate-900">{queSeBorra}</strong>.
                {advertencia ? ` ${advertencia}` : ''}
              </Dialog.Description>
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button type="button" variant="secondary">
                Cancelar
              </Button>
            </Dialog.Close>
            <Button type="button" variant="danger" isLoading={borrando} onClick={confirmar}>
              Eliminar
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
