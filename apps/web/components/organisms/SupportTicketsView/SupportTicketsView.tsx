'use client';

import { useId, useState } from 'react';
import { Eye, EyeOff, Inbox } from 'lucide-react';
import { Button, Textarea } from '@/components/atoms';
import { EmptyState, FormField } from '@/components/molecules';
import { useSupportTickets } from '@/lib/support-tickets-store';
import { useToast } from '@/lib/toast-store';
import { cn } from '@/lib/utils';
import type { SupportTicket } from '@ambienta/shared';
import { HistorialTimeline } from '@/components/organisms/HistorialTimeline';
import type { SupportTicketsViewProps } from './SupportTicketsView.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

const ESTADO_LABEL: Record<SupportTicket['estado'], string> = {
  abierto: 'Abierto',
  en_progreso: 'En progreso',
  cerrado: 'Cerrado',
};

/**
 * Estado del ticket con su propio tratamiento visual.
 *
 * Antes reutilizaba el semáforo de cumplimiento ambiental y un ticket recién
 * abierto se mostraba en rojo como "no cumple" — un ticket abierto no es un
 * incumplimiento normativo, es trabajo entrante. Mismo error que había en el
 * estado de los tenants.
 */
const ESTADO_ESTILO: Record<SupportTicket['estado'], string> = {
  abierto: 'bg-brand-50 text-brand-700',
  en_progreso: 'bg-semaforo-parcial-bg text-semaforo-parcial',
  cerrado: 'bg-slate-100 text-slate-600',
};

function EstadoTicket({ estado }: { estado: SupportTicket['estado'] }) {
  return (
    <span className={cn('inline-flex rounded-full px-2.5 py-1 text-xs font-medium', ESTADO_ESTILO[estado])}>
      {ESTADO_LABEL[estado]}
    </span>
  );
}

/**
 * S-38 Soporte/Tickets internos. Diferencia lo que ve el cliente de la vista
 * interna del equipo (RF-84), y la corrección de logs erróneos queda auditada
 * (RF-83).
 *
 * El historial del ticket ya no es una lista propia de `correcciones` sino el
 * audit log transversal (RF-32, RNF-08): así se ve la secuencia completa —
 * quién lo creó, quién lo tomó, cada cambio de estado y cada corrección — y
 * no solo las notas, que era lo único que se registraba antes.
 */
export function SupportTicketsView({ tickets, tenantNombre, currentUserId }: SupportTicketsViewProps) {
  const { updateEstado, addCorreccion, setVisibilidad } = useSupportTickets();
  const { mostrarToast } = useToast();
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
    mostrarToast({
      tipo: 'exito',
      mensaje: 'Corrección registrada',
      descripcion: 'Quedó en el historial del ticket con tu nombre y la fecha.',
    });
  }

  function handleEstado(nuevo: SupportTicket['estado']) {
    if (!selected) return;
    const anterior = selected.estado;
    updateEstado(selected.id, nuevo);
    mostrarToast({
      tipo: 'exito',
      mensaje: `Ticket ${ESTADO_LABEL[nuevo].toLowerCase()}`,
      descripcion: 'El cambio quedó registrado en el historial.',
      onUndo: () => updateEstado(selected.id, anterior),
    });
  }

  function handleVisibilidad() {
    if (!selected) return;
    const nuevo = !selected.visibleParaCliente;
    setVisibilidad(selected.id, nuevo);
    mostrarToast({
      tipo: 'info',
      mensaje: nuevo ? 'Ticket visible para el cliente' : 'Ticket oculto al cliente',
      descripcion: nuevo
        ? 'El cliente puede ver este ticket y su estado.'
        : 'Solo el equipo interno puede verlo.',
      onUndo: () => setVisibilidad(selected.id, !nuevo),
    });
  }

  if (tickets.length === 0) {
    return (
      <EmptyState
        icono={Inbox}
        titulo="No hay tickets de soporte"
        descripcion="Cuando un cliente envíe una solicitud aparecerá aquí, con su historial completo."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
        <table className="w-full min-w-[520px] text-sm">
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
                className={cn(
                  'cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50',
                  selectedId === t.id && 'bg-brand-50/50',
                )}
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{t.numero}</p>
                  <p className="text-xs text-slate-500">{t.asunto}</p>
                </td>
                <td className="px-4 py-3 text-slate-500">{tenantNombre(t.tenantId)}</td>
                <td className="px-4 py-3">
                  <EstadoTicket estado={t.estado} />
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {t.visibleParaCliente ? (
                    <span className="inline-flex items-center gap-1 text-xs">
                      <Eye className="h-3.5 w-3.5" aria-hidden /> Cliente ve esto
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs">
                      <EyeOff className="h-3.5 w-3.5" aria-hidden /> Solo interno
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-4">
        {!selected ? (
          <EmptyState
            icono={Inbox}
            titulo="Selecciona un ticket"
            descripcion="Verás su detalle, podrás cambiar su estado y revisar el historial completo de lo que pasó con él."
          />
        ) : (
          <>
            <div className="rounded-card border border-slate-200 bg-white p-6">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    {selected.numero} · {formatFecha(selected.fecha)}
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-slate-900">{selected.asunto}</h2>
                </div>
                <EstadoTicket estado={selected.estado} />
              </div>

              <p className="mt-2 text-sm text-slate-600">{selected.descripcion}</p>
              <p className="mt-2 text-xs text-slate-500">
                {tenantNombre(selected.tenantId)} · Contacto: {selected.contactoNombre ?? 'Sin especificar'}
                {selected.contactoEmail ? ` · ${selected.contactoEmail}` : ''}
              </p>

              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
                <FormField label="Estado" htmlFor={`${formId}-estado`}>
                  <select
                    id={`${formId}-estado`}
                    className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                    value={selected.estado}
                    onChange={(e) => handleEstado(e.target.value as SupportTicket['estado'])}
                  >
                    {(['abierto', 'en_progreso', 'cerrado'] as const).map((e) => (
                      <option key={e} value={e}>
                        {ESTADO_LABEL[e]}
                      </option>
                    ))}
                  </select>
                </FormField>

                <Button
                  variant="secondary"
                  size="md"
                  className="shrink-0"
                  onClick={handleVisibilidad}
                  icon={selected.visibleParaCliente ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
                >
                  {selected.visibleParaCliente ? 'Ocultar al cliente' : 'Mostrar al cliente'}
                </Button>
              </div>

              <div className="mt-5 border-t border-slate-100 pt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Corregir logs erróneos
                </h3>
                <p className="mt-0.5 text-xs text-slate-500">
                  Queda registrado con tu nombre y la fecha, y no se puede editar después (RF-83).
                </p>
                <FormField label="Qué se corrigió" htmlFor={`${formId}-nota`} error={error ?? undefined} required>
                  <Textarea
                    id={`${formId}-nota`}
                    rows={2}
                    className="mt-2"
                    value={nota}
                    invalid={!!error}
                    onChange={(e) => setNota(e.target.value)}
                    placeholder="Ej: se corrigió la fecha de detección, estaba mal ingresada."
                  />
                </FormField>
                <Button size="md" className="mt-2" onClick={handleCorregir}>
                  Guardar corrección
                </Button>
              </div>
            </div>

            <HistorialTimeline
              entidadTipo="ticket_soporte"
              entidadId={selected.id}
              titulo="Historial del ticket"
              descripcionVacio="Cada cambio de estado, corrección o comentario quedará aquí con su autor y fecha."
            />
          </>
        )}
      </div>
    </div>
  );
}
