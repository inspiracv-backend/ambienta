/**
 * El hilo de comentarios en la pantalla (RF-111).
 *
 * ## Lo que vigila
 *
 * Los estados vacíos y lo que se pierde al fallar. Un hilo que se ve vacío
 * porque la consulta no volvió afirma «nadie dijo nada sobre este registro», y
 * eso es exactamente lo contrario de lo que este módulo viene a arreglar: el
 * cliente dijo que la información se pierde por correo.
 *
 * Y lo escrito: si el servidor rechaza el comentario, **el texto se queda**.
 * Vaciar el borrador pase lo que pase es cómo se pierde lo que alguien acaba
 * de redactar.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { HiloDeComentarios } from './HiloDeComentarios';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';
import { mockUsers } from '@/mocks/users';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();
const post = vi.fn();

vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: {
      ...real.api,
      get: (...a: unknown[]) => get(...a),
      post: (...a: unknown[]) => post(...a),
    },
  };
});

function envoltura({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>{children}</SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

const UN_HILO = [
  {
    id: 'c-1',
    author_user_id: 'u-1',
    author_name: 'Carlos Mendoza',
    body: 'La evidencia del portal no coincide con el periodo declarado.',
    parent_id: null,
    edited_at: null,
    menciones: [],
    created_at: '2026-09-05T12:00:00Z',
  },
  {
    id: 'c-2',
    author_user_id: 'u-2',
    author_name: 'Ana Rojas',
    body: 'Corregido, subi el comprobante nuevo.',
    parent_id: 'c-1',
    edited_at: '2026-09-05T14:00:00Z',
    menciones: ['u-1'],
    created_at: '2026-09-05T13:00:00Z',
  },
];

function responder(respuesta: unknown) {
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('/comentarios/')) {
      return respuesta instanceof Error
        ? Promise.reject(respuesta)
        : Promise.resolve(respuesta);
    }
    if (ruta.startsWith('/users/')) return Promise.resolve(mockUsers);
    if (ruta.startsWith('/tenants/')) return Promise.reject(new Error('401'));
    return Promise.resolve([]);
  });
}

function pintar() {
  return render(<HiloDeComentarios entityType="obligation" entityId="o-1" />, {
    wrapper: envoltura,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  iniciarSesionComo('admin_empresa');
});

describe('el hilo', () => {
  it('muestra cada comentario con su autor, y marca el editado', async () => {
    responder(UN_HILO);
    pintar();

    expect(await screen.findByText(/no coincide con el periodo/)).toBeInTheDocument();
    expect(screen.getByText('Carlos Mendoza')).toBeInTheDocument();
    // **`editado` se muestra.** Un comentario corregido después de que alguien
    // lo respondió cambia lo que quedó escrito.
    expect(screen.getByText(/editado/)).toBeInTheDocument();
  });

  it('el contador no se dibuja mientras no se sabe', async () => {
    get.mockImplementation(() => new Promise(() => {}));
    pintar();

    expect(await screen.findByText('Comprobando…')).toBeInTheDocument();
    // Un «0 comentarios» junto al título afirma que nadie comentó nunca, y
    // acá todavía no se preguntó.
    expect(screen.queryByText(/0 comentarios/)).not.toBeInTheDocument();
  });

  it('si la consulta falla lo dice, en vez de verse vacío', async () => {
    responder(new Error('se cayó'));
    pintar();

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent(/No se pudo cargar la conversación/);
    expect(screen.queryByText(/Nadie ha comentado/)).not.toBeInTheDocument();
  });

  it('sin comentarios lo dice, y eso sí es una respuesta', async () => {
    responder([]);
    pintar();

    expect(await screen.findByText(/Nadie ha comentado/)).toBeInTheDocument();
    expect(screen.getByText(/0 comentarios/)).toBeInTheDocument();
  });
});

describe('publicar', () => {
  it('manda el comentario y recarga el hilo', async () => {
    responder([]);
    post.mockResolvedValue({ id: 'c-9' });
    const usuario = userEvent.setup();
    pintar();

    await screen.findByText(/Nadie ha comentado/);
    await usuario.type(
      screen.getByLabelText(/Escribir un comentario/),
      'Queda pendiente el anexo',
    );
    await usuario.click(screen.getByRole('button', { name: 'Comentar' }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [ruta, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(ruta).toBe('/comentarios/');
    expect(cuerpo.entity_type).toBe('obligation');
    expect(cuerpo.body).toBe('Queda pendiente el anexo');
  });

  it('si el servidor lo rechaza, LO ESCRITO SE QUEDA', async () => {
    // Es la parte que importa. Vaciar el borrador pase lo que pase hace que
    // quien redactó un comentario largo lo pierda porque el servidor respondió
    // mal, y tenga que escribirlo de nuevo sin saber si se guardó.
    responder([]);
    post.mockRejectedValue(new Error('sin permiso'));
    const usuario = userEvent.setup();
    pintar();

    await screen.findByText(/Nadie ha comentado/);
    const caja = screen.getByLabelText(/Escribir un comentario/);
    await usuario.type(caja, 'Un texto que costó escribir');
    await usuario.click(screen.getByRole('button', { name: 'Comentar' }));

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(caja).toHaveValue('Un texto que costó escribir');
  });
});
