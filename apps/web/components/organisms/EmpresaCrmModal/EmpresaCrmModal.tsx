'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button, Input, Textarea } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { ESTADO_DE_EMPRESA, type EmpresaCrm, type EstadoDeEmpresa } from '@/lib/crm';
import type { DatosDeEmpresa, Resultado } from '@/lib/crm-empresas-store';

/**
 * Alta y edición de una empresa del CRM.
 *
 * ## Lo único obligatorio es el nombre
 *
 * Y es a propósito. Un prospecto entra al sistema en una llamada, cuando lo
 * único que se sabe es cómo se llama: exigir RUT o rubro obligaría a inventar
 * datos para poder guardarlo, y un RUT inventado es peor que un RUT ausente
 * — el sistema lo usa para identificar legalmente a la empresa.
 *
 * ## El estado empieza en «prospecto»
 *
 * Pasar a cliente no es un cambio de etiqueta: la empresa tiene que existir
 * como tenant en la plataforma para poder asociarle un contrato. Por eso el
 * selector ofrece los tres estados pero la promoción a contrato se hace desde
 * el trato, no desde acá.
 */
export function EmpresaCrmModal({
  open,
  onOpenChange,
  empresa,
  onGuardar,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `null` = alta. Con empresa = edición. */
  empresa: EmpresaCrm | null;
  onGuardar: (datos: DatosDeEmpresa) => Promise<Resultado>;
}) {
  const formId = useId();
  const [nombre, setNombre] = useState('');
  const [rut, setRut] = useState('');
  const [rubro, setRubro] = useState('');
  const [sitioWeb, setSitioWeb] = useState('');
  const [estado, setEstado] = useState<EstadoDeEmpresa>('prospect');
  const [notas, setNotas] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Al abrir hay que recargar: si no, se arrastra lo de la empresa anterior y
  // se editaría una con los datos de otra.
  useEffect(() => {
    if (!open) return;
    setNombre(empresa?.nombre ?? '');
    setRut(empresa?.rut ?? '');
    setRubro(empresa?.rubro ?? '');
    setSitioWeb(empresa?.sitioWeb ?? '');
    setEstado(empresa?.estado ?? 'prospect');
    setNotas(empresa?.notas ?? '');
    setError(null);
  }, [open, empresa]);

  const puedeGuardar = nombre.trim().length > 0 && !guardando;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!puedeGuardar) return;
    setGuardando(true);
    setError(null);

    const r = await onGuardar({
      nombre: nombre.trim(),
      rut,
      rubro,
      sitioWeb,
      estado,
      notas,
    });

    setGuardando(false);
    if (r.ok) {
      onOpenChange(false);
      return;
    }
    // **El error se queda en el formulario y no cierra el modal.** Cerrarlo
    // perdería lo que la persona escribió, y volver a tipearlo es el momento
    // en que se abandona la carga.
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
                {empresa ? `Editar ${empresa.nombre}` : 'Nueva empresa'}
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-slate-500">
                Solo el nombre es obligatorio. El resto se completa cuando se sepa.
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
                  placeholder="Ej: Constructora del Sur SpA"
                  required
                />
              </FormField>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField label="RUT" htmlFor={`${formId}-rut`} hint="Opcional.">
                  <Input
                    id={`${formId}-rut`}
                    value={rut}
                    onChange={(e) => setRut(e.target.value)}
                    placeholder="76.543.210-K"
                  />
                </FormField>
                <FormField label="Rubro" htmlFor={`${formId}-rubro`}>
                  <Input
                    id={`${formId}-rubro`}
                    value={rubro}
                    onChange={(e) => setRubro(e.target.value)}
                    placeholder="Construcción"
                  />
                </FormField>
              </div>

              <FormField label="Sitio web" htmlFor={`${formId}-web`}>
                <Input
                  id={`${formId}-web`}
                  value={sitioWeb}
                  onChange={(e) => setSitioWeb(e.target.value)}
                  placeholder="https://…"
                />
              </FormField>

              <FormField
                label="Estado"
                htmlFor={`${formId}-estado`}
                hint="Pasa a cliente cuando la empresa ya existe en la plataforma."
              >
                <select
                  id={`${formId}-estado`}
                  value={estado}
                  onChange={(e) => setEstado(e.target.value as EstadoDeEmpresa)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  {(Object.keys(ESTADO_DE_EMPRESA) as EstadoDeEmpresa[]).map((e) => (
                    <option key={e} value={e}>
                      {ESTADO_DE_EMPRESA[e]}
                    </option>
                  ))}
                </select>
              </FormField>

              <FormField label="Notas" htmlFor={`${formId}-notas`}>
                <Textarea
                  id={`${formId}-notas`}
                  rows={3}
                  value={notas}
                  onChange={(e) => setNotas(e.target.value)}
                  placeholder="Cómo llegó, quién la refirió, qué necesita…"
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
                {guardando ? 'Guardando…' : empresa ? 'Guardar cambios' : 'Crear empresa'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
