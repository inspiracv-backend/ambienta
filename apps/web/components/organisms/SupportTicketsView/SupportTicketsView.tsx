'use client';

import { useId, useState } from 'react';
import { Eye, EyeOff, Inbox } from 'lucide-react';
import { Button, StatusBadge } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useSupportTickets } from '@/lib/support-tickets-store';
import type { SupportTicket } from '@ambienta/shared';
import type { SupportTicketsViewProps } from './SupportTicketsView.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

function estadoSemaforo(estado: SupportTicket['estado']) {
  if (estado === 'cerrado') return 'cumple' as const;
  if (estado === 'en_progreso') return 'parcial' as const;
  return 'no_cumple' as const;
}

const ESTADO_LABEL: Record<SupportTicket['estado'], string> = {
  abierto: 'Abierto',
  en_progreso: 'En progreso',
  cerrado: 'Cerrado',
};

/**
 * S-38 Soporte/Tickets internos. Diferencia claramente lo que ve el cliente
 * (visibleParaCliente) de la vista interna del equipo (RF-62). La corrección
 * de logs erróneos queda auditada en `correcciones` (RF-61).
 */
export function SupportTicketsView({ tickets, tenantNombre, currentUserId }: SupportTicketsViewProps) {
  const { updateEstado, addCorreccion } = useSupportTickets();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [nota, setNota] = useState('');
  const [error, setError] = useState<string | null>(null);
  const formId = useId();

  const selected = tickets.find((t) => t.id === selectedId) ?? null;
  const ordenados = [...tickets].sort((a, b) => new Date(b.fecha).getTime() - new Date(a.fecha).getTime());

  function handleCorregir() {
    if (!selected) return;
    if (!nota.trim()) {
      setError('Describe qué se corrigió antes de guardar.');
      return;
    }
    addCorreccion(selected.id, currentUserId, nota.trim());
    setNota('');
    setError(null);
  }

  if (tickets.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
        <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
        No hay tickets de soporte registrados.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
        <table className="w-full min-w-[560px] text-sm">
          <caption className="sr-only">Tickets de soporte (vista interna)</caption>
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
              <th scope="col" className="px-4 py-3">Ticket</th>
              <th scope="col" className="px-4 py-3">Empresa</th>
              <th scope="col" className="px-4 py-3">Estado</th>
              <th scope="col" className="px-4 py-3">Visibilidad</th>
            </tr>
          </thead>
          <tbody>
            {ordenados.map((t) => (
              <tr
                key={t.id}
                onClick={() => setSelectedId(t.id)}
                className={`cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 ${selectedId === t.id ? 'bg-brand-50/50' : ''}`}
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{t.numero}</p>
                  <p className="text-xs text-slate-500">{t.asunto}</p>
                </td>
                <td className="px-4 py-3 text-slate-500">{tenantNombre(t.tenantId)}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={estadoSemaforo(t.estado)} />
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {t.visibleParaCliente ? (
                    <span className="inline-flex items-center gap-1"><Eye className="h-3.5 w-3.5" aria-hidden /> Cliente ve esto</span>
                  ) : (
                    <span className="inline-flex items-center gap-1"><EyeOff className="h-3.5 w-3.5" aria-hidden /> Solo interno</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        {!selected ? (
          <p className="text-sm text-slate-500">Selecciona un ticket para ver el detalle.</p>
        ) : (
          <div className="flex flex-col gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{selected.numero} · {formatFecha(selected.fecha)}</p>
              <h2 className="mt-1 text-lg font-semibold text-slate-900">{selected.asunto}</h2>
              <p className="mt-1 text-sm text-slate-600">{selected.descripcion}</p>
              <p className="mt-2 text-xs text-slate-500">
                Contacto: {selected.contactoNombre ?? 'Sin especificar'} {selected.contactoEmail ? `· ${selected.contactoEmail}` : ''}
              </p>
            </div>

            <FormField label="Estado" htmlFor={`${formId}-estado`}>
              <select
                id={`${formId}-estado`}
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
                value={selected.estado}
                onChange={(e) => updateEstado(selected.id, e.target.value as SupportTicket['estado'])}
              >
                {(['abierto', 'en_progreso', 'cerrado'] as const).map((e) => (
                  <option key={e} value={e}>
                    {ESTADO_LABEL[e]}
                  </option>
                ))}
              </select>
            </FormField>

            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Corregir logs erróneos (auditado)</h3>
              <FormField label="Nota de corrección" htmlFor={`${formId}-nota`} error={error ?? undefined}>
                <textarea
                  id={`${formId}-nota`}
                  rows={2}
                  className="w-full rounded-lg border border-slate-300 p-2 text-sm"
                  value={nota}
                  onChange={(e) => setNota(e.target.value)}
                />
              </FormField>
              <Button size="md" className="mt-2" onClick={handleCorregir}>
                Guardar corrección
              </Button>

              {selected.correcciones.length > 0 && (
                <ul className="mt-3 flex flex-col gap-1.5 border-t border-slate-100 pt-3 text-xs text-slate-500">
                  {selected.correcciones.map((c, i) => (
                    <li key={i}>
                      <span className="font-medium text-slate-700">{formatFecha(c.fecha)}:</span> {c.nota}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
