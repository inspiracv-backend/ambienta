'use client';

import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button } from '@/components/atoms';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import { computeNormCompliance } from '@/lib/legal-matrix';
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

  const previewPct = computeNormCompliance({
    ...norm,
    articulos: norm.articulos.map((a) => ({ ...a, incluidoEnCalculo: draft.get(a.id) ?? a.incluidoEnCalculo })),
  });

  function handleSave() {
    draft.forEach((incluido, articuloId) => setIncluidoEnCalculo(norm.id, articuloId, incluido));
    onOpenChange(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card bg-white p-6 shadow-lg">
          <div className="flex items-start justify-between">
            <Dialog.Title className="text-lg font-semibold text-slate-900">Configurar % de cumplimiento</Dialog.Title>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-1 text-sm text-slate-500">
            Selecciona qué artículos entran en el cálculo del % global de esta norma.
          </Dialog.Description>

          <ul className="mt-4 max-h-64 flex-col gap-2 overflow-y-auto">
            {norm.articulos.map((articulo) => (
              <li key={articulo.id} className="flex items-start gap-2 border-b border-slate-100 py-2 last:border-0">
                <input
                  type="checkbox"
                  id={`incluir-${articulo.id}`}
                  checked={draft.get(articulo.id) ?? articulo.incluidoEnCalculo}
                  onChange={(e) => setDraft((prev) => new Map(prev).set(articulo.id, e.target.checked))}
                  className="mt-1"
                />
                <label htmlFor={`incluir-${articulo.id}`} className="text-sm text-slate-700">
                  <span className="font-medium">{articulo.numero}</span> — {articulo.descripcion}
                </label>
              </li>
            ))}
          </ul>

          <div className="mt-4 rounded-lg bg-brand-50 px-4 py-3 text-sm">
            % de cumplimiento resultante: <span className="font-semibold text-brand-700">{Math.round(previewPct * 100)}%</span>
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="secondary">Cancelar</Button>
            </Dialog.Close>
            <Button onClick={handleSave}>Guardar</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
