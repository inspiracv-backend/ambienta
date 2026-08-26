'use client';

import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button } from '@/components/atoms';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { computeNormComplianceOrNull } from '@/lib/legal-matrix';
import type { ComplianceConfigModalProps } from './ComplianceConfigModal.types';

/**
 * S-11 Configuración del % de Cumplimiento (RF-13). Los cambios se aplican
 * recién al presionar Guardar — cancelar no debe afectar el cálculo real (H3).
 */
export function ComplianceConfigModal({ norm, open, onOpenChange }: ComplianceConfigModalProps) {
  const { setIncluidoEnCalculo } = useLegalMatrix();
  const [draft, setDraft] = useState(() => new Map(norm.articulos.map((a) => [a.id, a.incluidoEnCalculo])));

  useEffect(() => {
    if (open) setDraft(new Map(norm.articulos.map((a) => [a.id, a.incluidoEnCalculo])));
  }, [open, norm.articulos]);

  const incluido = (id: string, porDefecto: boolean) => draft.get(id) ?? porDefecto;
  const cuantosIncluidos = norm.articulos.filter((a) => incluido(a.id, a.incluidoEnCalculo)).length;

  const previewPct = computeNormComplianceOrNull({
    ...norm,
    articulos: norm.articulos.map((a) => ({ ...a, incluidoEnCalculo: incluido(a.id, a.incluidoEnCalculo) })),
  });

  function marcarTodos(valor: boolean) {
    setDraft(new Map(norm.articulos.map((a) => [a.id, valor])));
  }

  function handleSave() {
    draft.forEach((valor, articuloId) => setIncluidoEnCalculo(norm.id, articuloId, valor));
    onOpenChange(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        {/* Mismo cambio que en el dialogo de evaluar, y por la misma causa: la
            lista mostraba el texto completo de cada articulo dentro de 448 px.
            Con el articulado de la BCN, un solo item llenaba la ventanita
            entera y elegir cuales entran al calculo era imposible. */}
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-card bg-white shadow-lg">
          <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-6 pb-4">
            <div className="min-w-0">
              <Dialog.Title className="text-lg font-semibold text-slate-900">Configurar % de cumplimiento</Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-slate-500">
                Los artículos marcados son los que entran en el cálculo. Desmarcar uno lo saca del porcentaje,
                pero <span className="font-medium text-slate-600">no lo saca de la lista para evaluar</span>.
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="shrink-0 text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="flex items-center justify-between border-b border-slate-100 px-6 py-3">
            <p className="text-sm text-slate-600">
              <span className="font-semibold tabular-nums text-slate-800">{cuantosIncluidos}</span> de{' '}
              <span className="tabular-nums">{norm.articulos.length}</span> artículos incluidos
            </p>
            <div className="flex gap-2">
              <button type="button" onClick={() => marcarTodos(true)} className="text-xs font-medium text-brand-600 hover:underline">
                Incluir todos
              </button>
              <span className="text-xs text-slate-300" aria-hidden>|</span>
              <button type="button" onClick={() => marcarTodos(false)} className="text-xs font-medium text-brand-600 hover:underline">
                Quitar todos
              </button>
            </div>
          </div>

          <ul className="flex-1 overflow-y-auto px-6 py-2">
            {norm.articulos.map((articulo) => (
              <li key={articulo.id} className="border-b border-slate-100 last:border-0">
                <label
                  htmlFor={`incluir-${articulo.id}`}
                  className="flex cursor-pointer items-start gap-3 py-3 hover:bg-slate-50"
                >
                  <input
                    type="checkbox"
                    id={`incluir-${articulo.id}`}
                    checked={incluido(articulo.id, articulo.incluidoEnCalculo)}
                    onChange={(e) => setDraft((prev) => new Map(prev).set(articulo.id, e.target.checked))}
                    className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-brand-600"
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-slate-800">{articulo.numero}</span>
                    {/* Dos lineas y a otra cosa. Aca la persona elige por numero
                        de articulo; el texto completo esta en la tabla y en el
                        dialogo de evaluar, que son donde se lee para decidir. */}
                    <span className="mt-0.5 line-clamp-2 block text-sm text-slate-500">{articulo.descripcion}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>

          <div className="border-t border-slate-200 p-6 pt-4">
            <div className="rounded-lg bg-brand-50 px-4 py-3 text-sm text-slate-700">
              {previewPct === null ? (
                // Antes decia "0%", que es lo mismo que dice una norma
                // completamente incumplida. No son lo mismo y no deben leerse
                // igual.
                <>
                  Con esta selección <span className="font-medium">todavía no hay nada que calcular</span>: ninguno de los
                  artículos incluidos tiene respuesta Sí o No.
                </>
              ) : (
                <>
                  % de cumplimiento resultante:{' '}
                  <span className="text-base font-semibold tabular-nums text-brand-700">{Math.round(previewPct * 100)}%</span>
                </>
              )}
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button variant="secondary">Cancelar</Button>
              </Dialog.Close>
              <Button onClick={handleSave}>Guardar</Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
