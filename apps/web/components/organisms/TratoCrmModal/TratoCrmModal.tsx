'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import type { ContactoCrm, TratoCrm } from '@/lib/crm';
import type { DatosDeTrato, Resultado } from '@/lib/crm-empresas-store';

/** Las monedas que se ofrecen. `currency` es texto libre en la base, así que
 *  esto acota lo que se puede tipear mal, no lo que la base admite. */
const MONEDAS = ['CLP', 'USD', 'UF', 'EUR'];

/**
 * Alta y edición de una oportunidad de una empresa del CRM.
 *
 * ## La etapa no se elige acá, ni al crear ni al editar
 *
 * Al crear, la API pone el trato en la **primera etapa abierta** del pipeline.
 * Ofrecer un selector obligaría a repetir esa regla en el navegador, y si
 * alguien reordena las columnas y deja «Perdido» arriba, un trato nuevo
 * nacería perdido.
 *
 * Al editar, mover de columna **no es editar un campo**: gana, exige motivo al
 * perder, o reabre. Por eso vive en su propio endpoint y en su propio control
 * de la ficha, no en este formulario.
 *
 * ## El monto viaja como texto
 *
 * `amount` es un `numeric` de Postgres. Pasarlo por `Number` en el camino
 * perdería precisión en montos grandes, y un pipeline con cifras que no cuadran
 * es un pipeline que nadie usa para decidir.
 */
export function TratoCrmModal({
  open,
  onOpenChange,
  trato,
  contactos,
  onGuardar,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `null` = alta. Con trato = edición. */
  trato: TratoCrm | null;
  /** Los de esta empresa, para poder decir con quién se está negociando. */
  contactos: ContactoCrm[];
  onGuardar: (datos: DatosDeTrato) => Promise<Resultado>;
}) {
  const formId = useId();
  const [titulo, setTitulo] = useState('');
  const [monto, setMonto] = useState('');
  const [moneda, setMoneda] = useState('CLP');
  const [contactoId, setContactoId] = useState('');
  const [cierre, setCierre] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitulo(trato?.titulo ?? '');
    // `null` es **sin valorar**, y eso se muestra como campo vacío, no como 0.
    setMonto(trato?.monto === null || trato?.monto === undefined ? '' : String(trato.monto));
    setMoneda(trato?.moneda ?? 'CLP');
    setContactoId(trato?.contactoId ?? '');
    setCierre(trato?.cierreEstimado ?? '');
    setError(null);
  }, [open, trato]);

  const puedeGuardar = titulo.trim().length > 0 && !guardando;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!puedeGuardar) return;
    setGuardando(true);
    setError(null);

    const r = await onGuardar({
      titulo,
      monto,
      moneda,
      contactoId: contactoId || null,
      cierreEstimado: cierre,
    });

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
                {trato ? `Editar ${trato.titulo}` : 'Nueva oportunidad'}
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-slate-500">
                {trato
                  ? 'La etapa se cambia desde el listado, no acá: mover de columna cierra o reabre el trato.'
                  : 'Entra en la primera etapa abierta del pipeline.'}
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={enviar} className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
              <FormField label="Título" htmlFor={`${formId}-titulo`}>
                <Input
                  id={`${formId}-titulo`}
                  value={titulo}
                  onChange={(e) => setTitulo(e.target.value)}
                  placeholder="Ej: Implantación matriz legal 2027"
                  required
                />
              </FormField>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField
                  label="Monto"
                  htmlFor={`${formId}-monto`}
                  hint="Vacío = sin valorar, que no es lo mismo que cero."
                >
                  <Input
                    id={`${formId}-monto`}
                    inputMode="decimal"
                    value={monto}
                    onChange={(e) => setMonto(e.target.value)}
                    placeholder="1500000"
                  />
                </FormField>
                <FormField label="Moneda" htmlFor={`${formId}-moneda`}>
                  <select
                    id={`${formId}-moneda`}
                    value={moneda}
                    onChange={(e) => setMoneda(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  >
                    {MONEDAS.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </FormField>
              </div>

              <FormField
                label="Contacto"
                htmlFor={`${formId}-contacto`}
                hint="Con quién se está negociando. Opcional."
              >
                <select
                  id={`${formId}-contacto`}
                  value={contactoId}
                  onChange={(e) => setContactoId(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  <option value="">Sin contacto asignado</option>
                  {contactos.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                      {c.cargo ? ` · ${c.cargo}` : ''}
                    </option>
                  ))}
                </select>
              </FormField>

              <FormField
                label="Cierre estimado"
                htmlFor={`${formId}-cierre`}
                hint="Una fecha de calendario, sin hora."
              >
                <Input
                  id={`${formId}-cierre`}
                  type="date"
                  value={cierre}
                  onChange={(e) => setCierre(e.target.value)}
                />
              </FormField>

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
                {guardando ? 'Guardando…' : trato ? 'Guardar cambios' : 'Crear oportunidad'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
