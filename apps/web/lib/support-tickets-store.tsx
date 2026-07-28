'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { SupportTicket } from '@ambienta/shared';
import { mockSupportTickets } from '@/mocks/support-tickets';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';

const ESTADO_LABEL: Record<SupportTicket['estado'], string> = {
  abierto: 'Abierto',
  en_progreso: 'En progreso',
  cerrado: 'Cerrado',
};

interface SupportTicketsContextValue {
  tickets: SupportTicket[];
  createTicket: (input: {
    tenantId: string | null;
    tipoSolicitud: string;
    asunto: string;
    descripcion: string;
    contactoNombre?: string;
    contactoEmail?: string;
  }) => SupportTicket;
  updateEstado: (ticketId: string, estado: SupportTicket['estado']) => void;
  /** RF-83: corrección de logs erróneos. El motivo es obligatorio y queda auditado. */
  addCorreccion: (ticketId: string, autorId: string, nota: string) => void;
  /** RF-84: qué ve el cliente vs. el equipo interno. */
  setVisibilidad: (ticketId: string, visibleParaCliente: boolean) => void;
}

const SupportTicketsContext = createContext<SupportTicketsContextValue | null>(null);

/**
 * Vive en app/layout.tsx (no solo en el layout de (dashboard)) porque un
 * Cliente Invitado crea tickets desde /crear-ticket, fuera de la sesión
 * autenticada — el mismo dato debe verse luego en Soporte (Sección L, S-38).
 *
 * El registro de auditoría se hace **aquí, en el store**, y no en cada
 * pantalla que llama: si dependiera de los llamadores, cualquier vista nueva
 * que mute un ticket podría olvidar anotarlo y el historial quedaría con
 * huecos silenciosos — que es exactamente lo que RNF-08 no permite.
 */
export function SupportTicketsProvider({ children }: { children: ReactNode }) {
  const [tickets, setTickets] = useState<SupportTicket[]>(mockSupportTickets);
  const registrar = useRegistrarAuditoria();

  /** Etiqueta legible que se congela en el historial (número + asunto). */
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
      // RF-83 exige que corregir un log quede auditado: la nota ES el motivo.
      motivo: nota,
    });
  }

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
    <SupportTicketsContext.Provider value={{ tickets, createTicket, updateEstado, addCorreccion, setVisibilidad }}>
      {children}
    </SupportTicketsContext.Provider>
  );
}

export function useSupportTickets() {
  const ctx = useContext(SupportTicketsContext);
  if (!ctx) throw new Error('useSupportTickets debe usarse dentro de <SupportTicketsProvider>');
  return ctx;
}
