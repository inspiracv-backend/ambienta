'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { SupportTicket } from '@ambienta/shared';
import { mockSupportTickets } from '@/mocks/support-tickets';

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
  addCorreccion: (ticketId: string, autorId: string, nota: string) => void;
}

const SupportTicketsContext = createContext<SupportTicketsContextValue | null>(null);

/**
 * Vive en app/layout.tsx (no solo en el layout de (dashboard)) porque un
 * Cliente Invitado crea tickets desde /crear-ticket, fuera de la sesión
 * autenticada — el mismo dato debe verse luego en Soporte (Sección L, S-38).
 */
export function SupportTicketsProvider({ children }: { children: ReactNode }) {
  const [tickets, setTickets] = useState<SupportTicket[]>(mockSupportTickets);

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
    return nuevo;
  }

  function updateEstado(ticketId: string, estado: SupportTicket['estado']) {
    setTickets((prev) => prev.map((t) => (t.id === ticketId ? { ...t, estado } : t)));
  }

  function addCorreccion(ticketId: string, autorId: string, nota: string) {
    setTickets((prev) =>
      prev.map((t) =>
        t.id === ticketId ? { ...t, correcciones: [...t.correcciones, { fecha: new Date().toISOString(), autorId, nota }] } : t,
      ),
    );
  }

  return (
    <SupportTicketsContext.Provider value={{ tickets, createTicket, updateEstado, addCorreccion }}>
      {children}
    </SupportTicketsContext.Provider>
  );
}

export function useSupportTickets() {
  const ctx = useContext(SupportTicketsContext);
  if (!ctx) throw new Error('useSupportTickets debe usarse dentro de <SupportTicketsProvider>');
  return ctx;
}
