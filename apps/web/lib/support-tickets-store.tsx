'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { CorreccionTicket, SupportTicket } from '@ambienta/shared';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api, mensajeDeError } from '@/lib/api-client';
import { categoriaDesdeTipo } from '@/lib/acceso-invitado';

const ESTADO_LABEL: Record<SupportTicket['estado'], string> = {
  abierto: 'Abierto',
  en_progreso: 'En progreso',
  cerrado: 'Cerrado',
};

const ESTADO_API: Record<SupportTicket['estado'], string> = {
  abierto: 'open',
  en_progreso: 'in_progress',
  cerrado: 'closed',
};

/**
 * La base tiene seis estados y la pantalla tres. `assigned`, `waiting_user`,
 * `in_progress` y `resolved` se muestran como "En progreso": ninguno es
 * trabajo entrante ni cerrado.
 */
function estadoDesdeApi(status: unknown): SupportTicket['estado'] {
  if (status === 'open') return 'abierto';
  if (status === 'closed') return 'cerrado';
  return 'en_progreso';
}

function ticketDesdeApi(raw: Record<string, unknown>): SupportTicket {
  return {
    id: String(raw.id),
    // **Sin respaldo inventado.** Antes, si faltaba, se sorteaba un `TCK-####`
    // en el navegador: un número que no existe en la base y que el cliente
    // anotaría para hacer seguimiento.
    numero: String(raw.ticket_number ?? ''),
    tenantId: raw.tenant_id ? String(raw.tenant_id) : null,
    tipoSolicitud: String(raw.category ?? 'other'),
    asunto: String(raw.subject ?? ''),
    descripcion: String(raw.description ?? ''),
    estado: estadoDesdeApi(raw.status),
    fecha: String(raw.created_at ?? ''),
    contactoNombre: raw.guest_name ? String(raw.guest_name) : undefined,
    contactoEmail: raw.guest_email ? String(raw.guest_email) : undefined,
  };
}

function correccionDesdeApi(raw: Record<string, unknown>): CorreccionTicket {
  return {
    id: String(raw.id),
    fecha: String(raw.created_at ?? ''),
    autorId: raw.author_user_id ? String(raw.author_user_id) : null,
    nota: String(raw.body ?? ''),
  };
}

interface NuevoTicket {
  tenantId: string | null;
  tipoSolicitud: string;
  asunto: string;
  descripcion: string;
  contactoNombre?: string;
  contactoEmail?: string;
}

interface SupportTicketsContextValue {
  tickets: SupportTicket[];
  loading: boolean;
  /**
   * Por que la lista esta vacia, si es que fallo (#208).
   *
   * `null` = se pregunto y esto es lo que hay. Un texto = **no se pudo
   * preguntar**, y la pantalla tiene que decirlo: sin esto un fallo de red se
   * ve igual que "esta empresa no tiene ninguno".
   */
  errorDeCarga: string | null;
  /** Rechaza si la base no lo guardó. El número que devuelve es el de la base. */
  createTicket: (input: NuevoTicket) => Promise<SupportTicket>;
  /** Rechaza si la base no lo guardó; en ese caso la pantalla no cambia. */
  updateEstado: (ticketId: string, estado: SupportTicket['estado']) => Promise<void>;
  /** RF-83. Rechaza si la base no la guardó. */
  addCorreccion: (ticketId: string, nota: string) => Promise<CorreccionTicket>;
  /** Las correcciones guardadas de un ticket, en orden. */
  cargarCorrecciones: (ticketId: string) => Promise<CorreccionTicket[]>;
}

const SupportTicketsContext = createContext<SupportTicketsContextValue | null>(null);

export function SupportTicketsProvider({ children }: { children: ReactNode }) {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    api
      .get<Record<string, unknown>[]>('/support/tickets', { tenantId: user.tenantId })
      .then((data) => {
        if (cancelled) return;
        // **Se escribe siempre, incluso vacio** (#208): cero filas no es lo
        // mismo que "no se pudo preguntar", que va por el `catch`.
        setTickets(data.map(ticketDesdeApi));
      })
      .catch((e: unknown) => {
        // **Se dice que fallo.** Con la lista vacia y sin mensaje, la
        // pantalla afirma 'no hay nada' cuando la verdad es 'no se pudo
        // preguntar' — que es la misma mentira de #208 en su otra forma.
        setErrorDeCarga(mensajeDeError(e));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user?.tenantId]);

  function etiqueta(t: SupportTicket): string {
    return `${t.numero} — ${t.asunto}`;
  }

  /**
   * **Hasta el 13-sep este ticket nunca llegaba a la base.** Mandaba
   * `category: 'declaracion'` —la base acepta seis categorías en inglés— y sin
   * correo de contacto, así que la API lo rechazaba; el `.catch(() => {})` se
   * tragaba el error y la pantalla mostraba "Solicitud enviada" con un número
   * sorteado en el navegador.
   */
  async function createTicket(input: NuevoTicket): Promise<SupportTicket> {
    if (!input.tenantId) {
      throw new Error('La sesión no tiene empresa: no hay dónde registrar el ticket.');
    }
    const raw = await api.post<Record<string, unknown>>(
      '/support/tickets',
      {
        subject: input.asunto,
        description: input.descripcion,
        category: categoriaDesdeTipo(input.tipoSolicitud),
        guest_name: input.contactoNombre || null,
        // La API usa el autor de la sesión si lo identifica; el correo es lo
        // que permite responder cuando no (fallback de desarrollo).
        guest_email: input.contactoEmail || null,
      },
      { tenantId: input.tenantId },
    );
    const nuevo = ticketDesdeApi(raw);
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

  async function updateEstado(ticketId: string, estado: SupportTicket['estado']): Promise<void> {
    const anterior = tickets.find((t) => t.id === ticketId);
    if (!anterior || anterior.estado === estado) return;
    if (!user?.tenantId) throw new Error('La sesión no tiene empresa.');

    // Primero la base y después la pantalla: con el orden al revés, un rechazo
    // dejaba el estado nuevo a la vista y el viejo guardado.
    await api.patch(`/support/tickets/${ticketId}`, { status: ESTADO_API[estado] }, { tenantId: user.tenantId });
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

  /**
   * RF-83. **Antes solo existía en la pestaña**: se agregaba a una lista local
   * y la pantalla decía "Quedó en el historial del ticket con tu nombre". Ahora
   * es un mensaje `internal_note` —interno, el cliente no lo ve— cuyo autor
   * pone la API desde la sesión, y que no se puede reescribir (409).
   */
  async function addCorreccion(ticketId: string, nota: string): Promise<CorreccionTicket> {
    const ticket = tickets.find((t) => t.id === ticketId);
    if (!ticket) throw new Error('El ticket ya no está en la lista.');
    if (!user?.tenantId) throw new Error('La sesión no tiene empresa.');

    const raw = await api.post<Record<string, unknown>>(
      `/support/tickets/${ticketId}/messages`,
      { ticket_id: ticketId, body: nota, message_type: 'internal_note', is_internal: true },
      { tenantId: user.tenantId },
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

    return correccionDesdeApi(raw);
  }

  async function cargarCorrecciones(ticketId: string): Promise<CorreccionTicket[]> {
    if (!user?.tenantId) return [];
    const data = await api.get<Record<string, unknown>[]>(
      `/support/tickets/${ticketId}/messages`,
      { tenantId: user.tenantId },
    );
    return data.filter((m) => m.message_type === 'internal_note').map(correccionDesdeApi);
  }

  return (
    <SupportTicketsContext.Provider
      value={{ tickets, loading, errorDeCarga, createTicket, updateEstado, addCorreccion, cargarCorrecciones }}
    >
      {children}
    </SupportTicketsContext.Provider>
  );
}

export function useSupportTickets() {
  const ctx = useContext(SupportTicketsContext);
  if (!ctx) throw new Error('useSupportTickets debe usarse dentro de <SupportTicketsProvider>');
  return ctx;
}
