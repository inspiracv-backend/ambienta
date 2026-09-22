import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { SupportTicketsProvider, useSupportTickets } from './support-tickets-store';
import { AuditLogProvider } from './audit-log-store';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';
import { ApiError } from './api-client';

/**
 * Lo que la pantalla de tickets afirma, contra lo que la base guardó.
 *
 * Hasta el 13-sep: el ticket con cuenta nunca llegaba (categoría inválida,
 * error tragado, número sorteado), la corrección de RF-83 vivía en la pestaña
 * y "Mostrar al cliente" cambiaba un campo que la base no tiene.
 */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/soporte',
}));

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...args: unknown[]) => get(...args),
      post: (...args: unknown[]) => post(...args),
      patch: (...args: unknown[]) => patch(...args),
      delete: vi.fn(),
    },
  };
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuditLogProvider>
        <UsersProvider>
          <SessionProvider>
            <SupportTicketsProvider>{children}</SupportTicketsProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

const TICKET_API = {
  id: 'b0000000-0000-0000-0000-000000000001',
  tenant_id: 't-1',
  ticket_number: 'SUP-000123',
  category: 'data',
  subject: 'No carga la evidencia',
  description: 'El enlace no abre',
  status: 'open',
  created_at: '2026-09-13T12:00:00Z',
  guest_name: null,
  guest_email: null,
};

async function montar() {
  iniciarSesionComo('admin_empresa');
  const r = renderHook(() => useSupportTickets(), { wrapper });
  await waitFor(() => expect(r.result.current.loading).toBe(false));
  return r;
}

beforeEach(() => {
  vi.clearAllMocks();
  // Por URL: los demás providers (usuarios) también preguntan, y darles
  // tickets les borra la sesión.
  get.mockImplementation((url: string) =>
    Promise.resolve(url === '/support/tickets' ? [TICKET_API] : []),
  );
  window.localStorage.clear();
});

describe('createTicket', () => {
  it('manda una categoría que la base acepta y usa el número de la base', async () => {
    post.mockResolvedValue({ ...TICKET_API, id: 'nuevo', ticket_number: 'SUP-000124' });
    const { result } = await montar();

    let numero = '';
    await act(async () => {
      const t = await result.current.createTicket({
        tenantId: 't-1',
        tipoSolicitud: 'declaracion',
        asunto: 'Duda',
        descripcion: 'Detalle',
        contactoEmail: 'persona@empresa.cl',
      });
      numero = t.numero;
    });

    const [, cuerpo] = post.mock.calls[0];
    expect(cuerpo.category).toBe('data');
    expect(cuerpo.guest_email).toBe('persona@empresa.cl');
    expect(numero).toBe('SUP-000124');
  });

  it('si la base lo rechaza, rechaza y no lo agrega a la lista', async () => {
    post.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'Un ticket necesita autor' }));
    const { result } = await montar();
    // Se espera la lista antes de contar: `loading` baja una vez sin empresa
    // declarada y la sesión llega después. Contar antes daba 0 y, con la
    // suite cargada, la lista aparecía entre la cuenta y la aserción.
    await waitFor(() => expect(result.current.tickets).toHaveLength(1));
    const antes = result.current.tickets.length;

    await act(async () => {
      await expect(
        result.current.createTicket({
          tenantId: 't-1',
          tipoSolicitud: 'general',
          asunto: 'Duda',
          descripcion: 'Detalle',
        }),
      ).rejects.toBeInstanceOf(ApiError);
    });
    expect(result.current.tickets).toHaveLength(antes);
  });
});

describe('addCorreccion (RF-83)', () => {
  it('se guarda como nota interna del ticket', async () => {
    post.mockResolvedValue({
      id: 7,
      ticket_id: TICKET_API.id,
      author_user_id: 'u-1',
      message_type: 'internal_note',
      body: 'Se corrigió la fecha',
      is_internal: true,
      created_at: '2026-09-13T12:05:00Z',
    });
    const { result } = await montar();
    await waitFor(() => expect(result.current.tickets).toHaveLength(1));

    await act(async () => {
      await result.current.addCorreccion(TICKET_API.id, 'Se corrigió la fecha');
    });

    const [url, cuerpo] = post.mock.calls[0];
    expect(url).toBe(`/support/tickets/${TICKET_API.id}/messages`);
    expect(cuerpo).toMatchObject({ message_type: 'internal_note', is_internal: true });
    // El autor no lo manda la pantalla: lo pone la API desde la sesión.
    expect(cuerpo).not.toHaveProperty('author_user_id');
  });

  it('si la base la rechaza, la pantalla se entera', async () => {
    post.mockRejectedValue(new ApiError(500, 'Error', null));
    const { result } = await montar();
    await waitFor(() => expect(result.current.tickets).toHaveLength(1));
    await act(async () => {
      await expect(result.current.addCorreccion(TICKET_API.id, 'x')).rejects.toBeInstanceOf(ApiError);
    });
  });

  it('al cargar solo muestra notas internas, no la conversación con el cliente', async () => {
    const { result } = await montar();
    await waitFor(() => expect(result.current.tickets).toHaveLength(1));
    get.mockImplementation((url: string) =>
      Promise.resolve(
        url.endsWith('/messages')
          ? [
              { id: 1, message_type: 'comment', body: 'Hola', created_at: '2026-09-13T12:00:00Z' },
              { id: 2, message_type: 'internal_note', body: 'Corregido', created_at: '2026-09-13T12:01:00Z' },
            ]
          : [],
      ),
    );
    let notas: string[] = [];
    await act(async () => {
      notas = (await result.current.cargarCorrecciones(TICKET_API.id)).map((c) => c.nota);
    });
    expect(notas).toEqual(['Corregido']);
  });
});

describe('updateEstado', () => {
  it('si la base lo rechaza, el estado a la vista no cambia', async () => {
    patch.mockRejectedValue(new ApiError(500, 'Error', null));
    const { result } = await montar();
    await waitFor(() => expect(result.current.tickets).toHaveLength(1));

    await act(async () => {
      await expect(result.current.updateEstado(TICKET_API.id, 'cerrado')).rejects.toBeInstanceOf(ApiError);
    });
    expect(result.current.tickets[0].estado).toBe('abierto');
  });
});
