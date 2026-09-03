'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import type { ContactoCrm } from '@/lib/crm';
import type { DatosDeContacto, Resultado } from '@/lib/crm-empresas-store';

/**
 * Alta y edición de un contacto de una empresa del CRM.
 *
 * ## Solo el nombre es obligatorio
 *
 * Mismo criterio que la ficha de empresa: a un prospecto se le anota primero
 * el nombre de quien contestó el teléfono, y exigir correo obligaría a
 * inventarlo. Un correo inventado es peor que ninguno — el sistema lo usa para
 * escribirle.
 *
 * ## «Principal» es una decisión, no una etiqueta
 *
 * Un índice único impide dos principales por empresa. Marcar a alguien cuando
 * ya hay otro responde **409**, y el mensaje del servidor se muestra tal cual
 * en el formulario en vez de cerrarlo: cerrarlo perdería lo escrito y quien lo
 * escribió no sabría qué corregir.
 */
export function ContactoCrmModal({
  open,
  onOpenChange,
  contacto,
  onGuardar,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `null` = alta. Con contacto = edición. */
  contacto: ContactoCrm | null;
  onGuardar: (datos: DatosDeContacto) => Promise<Resultado>;
}) {
  const formId = useId();
  const [nombre, setNombre] = useState('');
  const [correo, setCorreo] = useState('');
  const [telefono, setTelefono] = useState('');
  const [cargo, setCargo] = useState('');
  const [esPrincipal, setEsPrincipal] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setNombre(contacto?.nombre ?? '');
    setCorreo(contacto?.correo ?? '');
    setTelefono(contacto?.telefono ?? '');
    setCargo(contacto?.cargo ?? '');
    setEsPrincipal(contacto?.esPrincipal ?? false);
    setError(null);
  }, [open, contacto]);

  const puedeGuardar = nombre.trim().length > 0 && !guardando;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!puedeGuardar) return;
    setGuardando(true);
    setError(null);

    const r = await onGuardar({ nombre, correo, telefono, cargo, esPrincipal });

    setGuardando(false);
    if (r.ok) {
      onOpenChange(false);
      return;
    }
    setError(r.error ?? 'No se pudo guardar.');
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col rounded-card bg-white shadow-lg">
          <div className="flex items-start justify-between border-b border-slate-200 p-6">
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                {contacto ? `Editar ${contacto.nombre}` : 'Nuevo contacto'}
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-slate-500">
                La persona con la que se habla en esa empresa.
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={enviar} className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
              <FormField label="Nombre" htmlFor={`${formId}-nombre`}>
                <Input
                  id={`${formId}-nombre`}
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  placeholder="Ej: Carla Miranda"
                  required
                />
              </FormField>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField label="Correo" htmlFor={`${formId}-correo`}>
                  <Input
                    id={`${formId}-correo`}
                    type="email"
                    value={correo}
                    onChange={(e) => setCorreo(e.target.value)}
                    placeholder="carla@empresa.cl"
                  />
                </FormField>
                <FormField label="Teléfono" htmlFor={`${formId}-telefono`}>
                  <Input
                    id={`${formId}-telefono`}
                    value={telefono}
                    onChange={(e) => setTelefono(e.target.value)}
                    placeholder="+56 9 1234 5678"
                  />
                </FormField>
              </div>

              <FormField label="Cargo" htmlFor={`${formId}-cargo`}>
                <Input
                  id={`${formId}-cargo`}
                  value={cargo}
                  onChange={(e) => setCargo(e.target.value)}
                  placeholder="Jefa de Medio Ambiente"
                />
              </FormField>

              <label className="flex items-start gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={esPrincipal}
                  onChange={(e) => setEsPrincipal(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span>
                  Contacto principal
                  <span className="block text-xs text-slate-500">
                    Solo puede haber uno por empresa. Si ya hay otro, el servidor lo rechaza.
                  </span>
                </span>
              </label>

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
              <Button type="submit" disabled={!puedeGuardar}>
                {guardando ? 'Guardando…' : contacto ? 'Guardar cambios' : 'Crear contacto'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
