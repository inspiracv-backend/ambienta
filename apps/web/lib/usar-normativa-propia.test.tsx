/**
 * La normativa propia en el navegador (RF-10, RF-11).
 *
 * ## Lo que vigila
 *
 * Que la pantalla **no acuse a la empresa**. Una lista vacía en este módulo se
 * lee como «esta empresa no cargó su RCA», que es afirmar que le falta un
 * permiso ambiental — y hay tres formas de llegar a ella:
 *
 * | estado | significa |
 * |---|---|
 * | `null` | la consulta no volvió |
 * | error | no se pudo preguntar |
 * | `[]` | se preguntó y no hay ninguna registrada |
 *
 * Y que **cero considerandos no se esconda**: es el estado inicial mientras se
 * transcriben, no un defecto.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react';
import type { ReactNode } from 'react';
import { useNormativaPropia } from './usar-normativa-propia';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';
import { mockUsers } from '@/mocks/users';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();
const post = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
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

const UNA_RCA = [
  {
    id: 'n-1',
    tenant_id: 'a0000000-0000-0000-0000-000000000001',
    source_id: 3,
    norm_type: 'resolucion',
    norm_number: 'RCA-123/2019',
    title: 'RCA Planta Rancagua',
    issuing_body: 'Comisión de Evaluación Ambiental',
    publication_date: '2019-04-10',
    articulos: 0,
  },
];

function responder(respuesta: unknown) {
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('/normativa-propia')) {
      return respuesta instanceof Error
        ? Promise.reject(respuesta)
        : Promise.resolve(respuesta);
    }
    if (ruta.startsWith('/users/')) return Promise.resolve(mockUsers);
    if (ruta.startsWith('/tenants/')) return Promise.reject(new Error('401'));
    return Promise.resolve([]);
  });
}

const montar = () => renderHook(() => useNormativaPropia(), { wrapper: envoltura });

beforeEach(() => {
  vi.clearAllMocks();
  iniciarSesionComo('admin_empresa');
});

describe('la lista', () => {
  it('trae la RCA con su número, que es lo que se cita', async () => {
    responder(UNA_RCA);
    const { result } = montar();

    await waitFor(() => expect(result.current.normas).not.toBeNull());
    const [n] = result.current.normas!;
    expect(n.normNumber).toBe('RCA-123/2019');
    expect(n.organismo).toContain('Evaluación');
    // **Cero considerandos se conserva como cero**, no se convierte en nada:
    // es el estado inicial mientras se transcriben.
    expect(n.articulos).toBe(0);
  });

  it('mientras no vuelve la consulta, no hay lista', async () => {
    get.mockImplementation(() => new Promise(() => {}));
    const { result } = montar();

    await new Promise((r) => setTimeout(r, 30));
    expect(result.current.normas).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('si falla lo dice, en vez de parecer que no hay ninguna', async () => {
    responder(new Error('se cayó'));
    const { result } = montar();

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error).toBeTruthy();
    expect(result.current.normas).toEqual([]);
  });
});

describe('registrar', () => {
  it('manda la fuente y el título, y recarga', async () => {
    responder([]);
    post.mockResolvedValue({ id: 'n-9' });
    const { result } = montar();
    await waitFor(() => expect(result.current.normas).not.toBeNull());

    await act(async () => {
      await result.current.registrar({ fuente: 'RCA', title: 'RCA nueva' });
    });

    const [ruta, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(ruta).toBe('/compliance/normativa-propia/');
    expect(cuerpo.fuente).toBe('RCA');
    // Se vuelve a pedir la lista: sin eso la pantalla mostraría el estado de
    // antes de la acción que la persona acaba de hacer.
    await waitFor(() =>
      expect(
        get.mock.calls.filter((c) => String(c[0]).includes('/normativa-propia')).length,
      ).toBeGreaterThan(1),
    );
  });

  it('si el servidor rechaza, devuelve false y lo dice', async () => {
    // El componente sólo limpia el formulario cuando esto es `true`: el número
    // de una RCA cuesta ir a buscarlo.
    responder([]);
    post.mockRejectedValue(new Error('sin permiso'));
    const { result } = montar();
    await waitFor(() => expect(result.current.normas).not.toBeNull());

    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.registrar({ fuente: 'RCA', title: 'X' });
    });

    expect(ok).toBe(false);
    expect(result.current.errorAlGuardar).toBeTruthy();
  });
});
