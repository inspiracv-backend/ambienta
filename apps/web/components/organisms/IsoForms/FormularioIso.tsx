'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import type { CampoIso, FormularioIsoProps } from './IsoForms.types';

/**
 * El formulario de alta y edición de las tres pantallas ISO.
 *
 * ## Por qué uno solo y no tres
 *
 * Aspectos, riesgos y equipos se editan igual: un puñado de campos de texto,
 * unos cuantos desplegables y una fecha. Tres modales casi idénticos se
 * separan con el tiempo —uno valida al enviar y otro al escribir, uno cierra
 * al guardar y otro no— y la persona aprende tres comportamientos para la
 * misma acción.
 *
 * Lo que cambia entre pantallas son los campos, y eso viaja como dato.
 *
 * ## Los campos son los que la base guarda, y nada más
 *
 * `packages/shared` define estas entidades con más campos de los que existen
 * en la base. **No se ofrecen.** Un campo que se escribe y no se persiste es
 * la forma más silenciosa de perder un dato: se ve "guardado", se recarga y no
 * está. Ya pasó en este repositorio con `evidence_url`.
 */
export function FormularioIso({
  open,
  onOpenChange,
  titulo,
  descripcion,
  campos,
  valores,
  onGuardar,
}: FormularioIsoProps) {
  const formId = useId();
  const [datos, setDatos] = useState<Record<string, string>>({});
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);

  // Al abrir —o al cambiar de fila— el formulario parte de lo que hay. Sin
  // esto, editar una fila después de otra mostraría los valores de la anterior.
  useEffect(() => {
    if (!open) return;
    const inicial: Record<string, string> = {};
    for (const campo of campos) {
      const v = valores?.[campo.nombre];
      inicial[campo.nombre] = v === null || v === undefined ? '' : String(v);
    }
    setDatos(inicial);
    setErrores({});
  }, [open, campos, valores]);

  function validar(campo: CampoIso, valor: string): string | null {
    if (campo.requerido && !valor.trim()) return `${campo.etiqueta} es obligatorio.`;
    if (campo.tipo === 'numero' && valor.trim()) {
      const n = Number(valor);
      if (Number.isNaN(n)) return 'Tiene que ser un número.';
      if (campo.min !== undefined && n < campo.min) return `Mínimo ${campo.min}.`;
      if (campo.max !== undefined && n > campo.max) return `Máximo ${campo.max}.`;
    }
    return null;
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const fallos: Record<string, string> = {};
    for (const campo of campos) {
      const msg = validar(campo, datos[campo.nombre] ?? '');
      if (msg) fallos[campo.nombre] = msg;
    }
    setErrores(fallos);
    if (Object.keys(fallos).length > 0) return;

    // Lo vacío viaja como `null` y no como `""`: la base distingue "no se sabe"
    // de "está en blanco", y mandar cadenas vacías llenaría columnas opcionales
    // de valores que parecen datos.
    const cuerpo: Record<string, unknown> = {};
    for (const campo of campos) {
      const bruto = (datos[campo.nombre] ?? '').trim();
      if (!bruto) {
        if (!campo.requerido) cuerpo[campo.nombre] = null;
        continue;
      }
      cuerpo[campo.nombre] = campo.tipo === 'numero' ? Number(bruto) : bruto;
    }

    setEnviando(true);
    const ok = await onGuardar(cuerpo);
    setEnviando(false);
    if (ok) onOpenChange(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-card bg-white p-6 shadow-lg">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                {titulo}
              </Dialog.Title>
              {descripcion && (
                <Dialog.Description className="text-sm text-slate-500">
                  {descripcion}
                </Dialog.Description>
              )}
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={enviar} className="mt-5 grid gap-4 sm:grid-cols-2" noValidate>
            {campos.map((campo) => {
              const id = `${formId}-${campo.nombre}`;
              const valor = datos[campo.nombre] ?? '';
              const cambiar = (v: string) =>
                setDatos((prev) => ({ ...prev, [campo.nombre]: v }));

              return (
                <div
                  key={campo.nombre}
                  className={campo.tipo === 'textarea' ? 'sm:col-span-2' : undefined}
                >
                  <FormField
                    label={campo.etiqueta}
                    htmlFor={id}
                    required={campo.requerido}
                    error={errores[campo.nombre]}
                    hint={campo.ayuda}
                  >
                    {campo.tipo === 'select' ? (
                      <select
                        id={id}
                        className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                        value={valor}
                        onChange={(e) => cambiar(e.target.value)}
                      >
                        {!campo.requerido && <option value="">—</option>}
                        {(campo.opciones ?? []).map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    ) : campo.tipo === 'textarea' ? (
                      <textarea
                        id={id}
                        rows={3}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        value={valor}
                        onChange={(e) => cambiar(e.target.value)}
                      />
                    ) : (
                      <Input
                        id={id}
                        type={
                          campo.tipo === 'numero'
                            ? 'number'
                            : campo.tipo === 'fecha'
                              ? 'date'
                              : 'text'
                        }
                        min={campo.min}
                        max={campo.max}
                        value={valor}
                        invalid={!!errores[campo.nombre]}
                        onChange={(e) => cambiar(e.target.value)}
                      />
                    )}
                  </FormField>
                </div>
              );
            })}

            <div className="flex justify-end gap-2 sm:col-span-2">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">
                  Cancelar
                </Button>
              </Dialog.Close>
              <Button type="submit" isLoading={enviando}>
                Guardar
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
