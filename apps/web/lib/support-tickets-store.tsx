'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { SupportTicket } from '@ambienta/shared';
import { mockSupportTickets } from '@/mocks/support-tickets';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api } from '@/lib/api-client';

const ESTADO_LABEL: Record<SupportTicket['estado'], string> = {
  abierto: 'Abierto',
  en_progreso: 'En progreso',
  cerrado: 'Cerrado',
};

interface SupportTicketsContextValue {
  tickets: SupportTicket[];
  loading: boolean;
  createTicket: (input: {
    tenantId: string | null;
    tipoSolicitud: string;
    asunto: string;
    descripcion: string;
    contactoNombre?: string;
    contactoEmail?: string;
  }) => SupportTicket;
  updateEstado: (ticketId: string, estado: SupportTicket['estado']) => void;
  addCorreccion: (ticketId: string, autorId: string, nota: string) => void;
  setVisibilidad: (ticketId: string, visibleParaCliente: boolean) => void;
}

const SupportTicketsContext = createContext<SupportTicketsContextValue | null>(null);

export function SupportTicketsProvider({ children }: { children: ReactNode }) {
  const [tickets, setTickets] = useState<SupportTicket[]>(mockSupportTickets);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    api
      .get<Record<string, unknown>[]>('/support/tickets', { tenantId: user.tenantId })
      .then((data) => {
        if (cancelled) return;
        const mapped: SupportTicket[] = data.map((raw) => ({
          id: String(raw.id),
          numero: String(raw.ticket_number ?? `TCK-${Math.floor(1000 + Math.random() * 9000)}`),
          tenantId: raw.tenant_id ? String(raw.tenant_id) : null,
          tipoSolicitud: String(raw.category ?? 'general'),
          asunto: String(raw.subject ?? ''),
          descripcion: String(raw.description ?? ''),
          estado: (raw.status === 'open' ? 'abierto' : raw.status === 'closed' ? 'cerrado' : 'en_progreso') as SupportTicket['estado'],
          fecha: String(raw.created_at ?? new Date().toISOString()),
          visibleParaCliente: true,
          correcciones: [],
        }));
        if (mapped.length > 0) setTickets(mapped);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user?.tenantId]);

  function etiqueta(t: SupportTicket): string {
    return `${t.numero} — ${t.asunto}`;
  }

  function createTicket(input: {
    tenantId: string | null;
    tipoSolicitud: string;
    asunto: string;
    descripcion: string;
    contactoNombre?: string;
    contactoEmail?: string;
  }): SupportTicket {
    const nuevo: SupportTicket = {
      id: `ticket-${Date.now()}`,
      numero: `TCK-${Math.floor(1000 + Math.random() * 9000)}`,
      tenantId: input.tenantId,
      tipoSolicitud: input.tipoSolicitud,
      asunto: input.asunto,
      descripcion: input.descripcion,
      estado: 'abierto',
      fecha: new Date().toISOString(),
      contactoNombre: input.contactoNombre,
      contactoEmail: input.contactoEmail,
      visibleParaCliente: true,
      correcciones: [],
    };
    setTickets((prev) => [...prev, nuevo]);

    if (input.tenantId) {
      api.post('/support/tickets', {
        subject: input.asunto,
        description: input.descripcion,
        category: input.tipoSolicitud,
      }, { tenantId: input.tenantId }).catch(() => {});
    }

    registrar({
      entidadTipo: 'ticket_soporte',
      entidadId: nuevo.id,
      entidadLabel: etiqueta(nuevo),
      tenantId: nuevo.tenantId,
      accion: 'creado',
      resumen: 'Creó el ticket',
      cambios: [
        { campo: 'Tipo de solicitud', antes: null, despues: input.tipoSolicitud },
        { campo: 'Estado', antes: null, despues: ESTADO_LABEL.abierto },
      ],
    });

    return nuevo;
  }

  function updateEstado(ticketId: string, estado: SupportTicket['estado']) {
    const anterior = tickets.find((t) => t.id === ticketId);
    if (!anterior || anterior.estado === estado) return;

    setTickets((prev) => prev.map((t) => (t.id === ticketId ? { ...t, estado } : t)));

    if (user?.tenantId) {
      api.patch(`/support/tickets/${ticketId}`, {
        status: estado === 'abierto' ? 'open' : estado === 'cerrado' ? 'closed' : 'in_progress',
      }, { tenantId: user.tenantId }).catch(() => {});
    }

    registrar({
      entidadTipo: 'ticket_soporte',
      entidadId: ticketId,
      entidadLabel: etiqueta(anterior),
      tenantId: anterior.tenantId,
      accion: estado === 'cerrado' ? 'cerrado' : 'estado_cambiado',
      resumen:
        estado === 'cerrado'
          ? 'Cerró el ticket'
          : `Cambió el estado a ${ESTADO_LABEL[estado].toLowerCase()}`,
      cambios: [{ campo: 'Estado', antes: ESTADO_LABEL[anterior.estado], despues: ESTADO_LABEL[estado] }],
    });
  }

  function addCorreccion(ticketId: string, autorId: string, nota: string) {
    const ticket = tickets.find((t) => t.id === ticketId);
    if (!ticket) return;

    setTickets((prev) =>
      prev.map((t) =>
        t.id === ticketId ? { ...t, correcciones: [...t.correcciones, { fecha: new Date().toISOString(), autorId, nota }] } : t,
      ),
    );

    registrar({
      entidadTipo: 'ticket_soporte',
      entidadId: ticketId,
      entidadLabel: etiqueta(ticket),
      tenantId: ticket.tenantId,
      accion: 'comentado',
      resumen: 'Registró una corrección',
      motivo: nota,
    });
  }

  /**
   * **No llega a la base:** `SupportTicketUpdate` acepta `status`, `priority` y
   * `assigned_to`. No hay campo de visibilidad para el cliente.
   *
   * Ojo con confundirlo con `is_internal` de los mensajes: ese existe, pero es
   * por mensaje, no por ticket, y significa otra cosa.
   */
  function setVisibilidad(ticketId: string, visibleParaCliente: boolean) {
    const ticket = tickets.find((t) => t.id === ticketId);
    if (!ticket || ticket.visibleParaCliente === visibleParaCliente) return;

    setTickets((prev) => prev.map((t) => (t.id === ticketId ? { ...t, visibleParaCliente } : t)));

    registrar({
      entidadTipo: 'ticket_soporte',
      entidadId: ticketId,
      entidadLabel: etiqueta(ticket),
      tenantId: ticket.tenantId,
      accion: 'actualizado',
      resumen: visibleParaCliente ? 'Hizo el ticket visible para el cliente' : 'Ocultó el ticket al cliente',
      cambios: [
        {
          campo: 'Visible para el cliente',
          antes: ticket.visibleParaCliente ? 'Sí' : 'No',
          despues: visibleParaCliente ? 'Sí' : 'No',
        },
      ],
    });
  }

  return (
    <SupportTicketsContext.Provider value={{ tickets, loading, createTicket, updateEstado, addCorreccion, setVisibilidad }}>
      {children}
    </SupportTicketsContext.Provider>
  );
}

export function useSupportTickets() {
  const ctx = useContext(SupportTicketsContext);
  if (!ctx) throw new Error('useSupportTickets debe usarse dentro de <SupportTicketsProvider>');
  return ctx;
}
