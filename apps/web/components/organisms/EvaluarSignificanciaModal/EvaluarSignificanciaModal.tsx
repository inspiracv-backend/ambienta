'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useIso, type AspectoApi } from '@/lib/iso-store';

export interface EvaluarSignificanciaModalProps {
  aspecto: AspectoApi | null;
  onOpenChange: (open: boolean) => void;
}

const PUNTAJES = Array.from({ length: 10 }, (_, i) => i + 1);

const CRITERIOS = [
  {
    campo: 'frequency_score' as const,
    etiqueta: 'Frecuencia',
    ayuda: 'Cuántas veces ocurre. 1 = excepcional, 10 = permanente.',
  },
  {
    campo: 'severity_score' as const,
    etiqueta: 'Severidad',
    ayuda: 'Qué tan grave es el impacto. 1 = leve, 10 = grave.',
  },
  {
    campo: 'legal_score' as const,
    etiqueta: 'Requisito legal',
    ayuda: 'Qué tan directamente lo alcanza una obligación legal. 8 o más lo vuelve significativo por sí solo.',
  },
];

/**
 * Evaluar la significancia de un aspecto (ISO 14001 §6.1.2, #44).
 *
 * **El veredicto lo decide el servidor**, no esta pantalla: la regla vivía en
 * el navegador y dos clientes con la misma matriz podían discrepar sin que
 * nadie pudiera auditar el criterio. Aquí se cargan los tres puntajes y se
 * muestra lo que respondió, incluidos los motivos.
 *
 * Hasta el 19-sep no existía: el endpoint estaba escrito y probado, y **ninguna
 * pantalla lo llamaba**, así que todos los aspectos quedaban "Sin evaluar" y el
 * filtro "significativo sin tratar" no podía encontrar nada. Los tres puntajes
 * estaban en el formulario de edición, que los guarda **sin calcular nada**: se
 * sacaron de ahí para que la significancia tenga un solo camino.
 */
export function EvaluarSignificanciaModal({ aspecto, onOpenChange }: EvaluarSignificanciaModalProps) {
  const formId = useId();
  const { evaluarSignificancia } = useIso();
  const [puntajes, setPuntajes] = useState({ frequency_score: 5, severity_score: 5, legal_score: 1 });
  const [resultado, setResultado] = useState<{ significancia: string; motivos: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!aspecto) return;
    setResultado(null);
    setError(null);
    setPuntajes({
      frequency_score: aspecto.puntajeFrecuencia ?? 5,
      severity_score: aspecto.puntajeSeveridad ?? 5,
      legal_score: aspecto.puntajeLegal ?? 1,
    });
  }, [aspecto]);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!aspecto) return;
    setEnviando(true);
    setError(null);
    const r = await evaluarSignificancia(aspecto.id, puntajes);
    setEnviando(false);
    if (r.ok) setResultado({ significancia: r.significancia, motivos: r.motivos });
    else setError(r.error);
  }

  const select = 'h-11 w-full rounded-lg border border-slate-300 px-3 text-sm';

  return (
    <Dialog.Root open={aspecto !== null} onOpenChange={(v) => !v && onOpenChange(false)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-card bg-white p-6 shadow-lg">
          <div className="flex items-start justify-between">
            <Dialog.Title className="text-lg font-semibold text-slate-900">Evaluar significancia</Dialog.Title>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-1 text-xs text-slate-500">
            {aspecto ? `${aspecto.actividad} — ${aspecto.aspecto}. ` : ''}
            El veredicto lo calcula el servidor con los criterios de la empresa.
          </Dialog.Description>

          <form onSubmit={enviar} className="mt-4 flex flex-col gap-4" noValidate>
            {CRITERIOS.map((c) => (
              <FormField key={c.campo} label={c.etiqueta} htmlFor={`${formId}-${c.campo}`} hint={c.ayuda} required>
                <select
                  id={`${formId}-${c.campo}`}
                  className={select}
                  value={puntajes[c.campo]}
                  onChange={(e) => setPuntajes((p) => ({ ...p, [c.campo]: Number(e.target.value) }))}
                >
                  {PUNTAJES.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </FormField>
            ))}

            {resultado && (
              <div
                role="status"
                className={`rounded-lg border p-3 text-sm ${
                  resultado.significancia === 'significant'
                    ? 'border-semaforo-no-cumple/30 bg-semaforo-no-cumple-bg text-slate-800'
                    : 'border-slate-200 bg-slate-50 text-slate-700'
                }`}
              >
                <p className="font-semibold">
                  {resultado.significancia === 'significant' ? 'Significativo' : 'No significativo'}
                </p>
                <ul className="mt-1 list-disc pl-5">
                  {resultado.motivos.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
            )}

            {error && (
              <p role="alert" className="text-sm text-semaforo-no-cumple">
                No se evaluó: {error}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">
                  {resultado ? 'Cerrar' : 'Cancelar'}
                </Button>
              </Dialog.Close>
              <Button type="submit" disabled={enviando}>
                {enviando ? 'Evaluando…' : resultado ? 'Volver a evaluar' : 'Evaluar'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
