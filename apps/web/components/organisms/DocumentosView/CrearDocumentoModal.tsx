'use client';

import { useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import {
  ETIQUETA_TIPO_DOCUMENTO,
  TIPOS_DOCUMENTO_CONTROLADO,
} from '@ambienta/shared';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useDocumentos } from '@/lib/documentos-store';
import type { CrearDocumentoModalProps } from './DocumentosView.types';

/**
 * Alta de un documento controlado (RF-102).
 *
 * ## El archivo no se pide acá, y es a propósito
 *
 * Crear el documento y subirle una revisión son dos pasos, porque son dos cosas
 * distintas: el documento es la identidad estable —código, título, tipo— y la
 * revisión es un archivo con su propio ciclo de vida. Juntarlos obligaría a
 * tener el archivo listo para poder registrar el documento, y en la práctica se
 * define primero qué procedimiento hace falta y después se escribe.
 *
 * ## Sólo se ofrecen los tipos controlados
 *
 * Los otros que admite el modelo —evidencias, comprobantes, adjuntos de
 * correo— **los crea el sistema** al adjuntar algo a una obligación o a una
 * declaración. Ofrecerlos acá invitaría a crear a mano un comprobante que
 * debería venir de un portal del Estado.
 */
export function CrearDocumentoModal({
  open,
  onOpenChange,
  onCreado,
}: CrearDocumentoModalProps) {
  const { crear } = useDocumentos();
  const formId = useId();

  const [titulo, setTitulo] = useState('');
  const [tipo, setTipo] = useState<string>('procedimiento');
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);

  function limpiar() {
    setTitulo('');
    setTipo('procedimiento');
    setErrores({});
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!titulo.trim()) {
      setErrores({ titulo: 'Ponle un título al documento.' });
      return;
    }
    setErrores({});
    setEnviando(true);
    const doc = await crear({ titulo: titulo.trim(), tipo });
    setEnviando(false);
    if (doc) {
      onCreado(doc.id);
      onOpenChange(false);
      limpiar();
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) limpiar();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
          <div className="flex items-start justify-between">
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                Nuevo documento
              </Dialog.Title>
              <Dialog.Description className="text-sm text-slate-500">
                Primero se registra el documento; el archivo se sube después, como
                revisión.
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={enviar} className="mt-5 flex flex-col gap-4" noValidate>
            <FormField
              label="Título"
              htmlFor={`${formId}-titulo`}
              required
              error={errores.titulo}
            >
              <Input
                id={`${formId}-titulo`}
                value={titulo}
                invalid={!!errores.titulo}
                placeholder="Ej.: Procedimiento de manejo de residuos peligrosos"
                onChange={(e) => setTitulo(e.target.value)}
              />
            </FormField>

            <FormField label="Tipo" htmlFor={`${formId}-tipo`}>
              <select
                id={`${formId}-tipo`}
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                value={tipo}
                onChange={(e) => setTipo(e.target.value)}
              >
                {TIPOS_DOCUMENTO_CONTROLADO.map((t) => (
                  <option key={t} value={t}>
                    {ETIQUETA_TIPO_DOCUMENTO[t] ?? t}
                  </option>
                ))}
              </select>
            </FormField>

            <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
              El <strong>código</strong> lo asigna la empresa según su propia
              nomenclatura y se edita después. No se inventa uno automático: es lo que
              se cita en una auditoría, y un código generado por el sistema no
              coincidiría con el que la empresa ya usa en papel.
            </p>

            <div className="flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">
                  Cancelar
                </Button>
              </Dialog.Close>
              <Button type="submit" isLoading={enviando}>
                Crear documento
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
