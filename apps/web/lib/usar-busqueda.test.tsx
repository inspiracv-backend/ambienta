/**
 * El buscador transversal en el navegador (RF-114).
 *
 * ## Lo que vigila
 *
 * Los estados, que en un buscador se confunden más que en ninguna otra
 * pantalla:
 *
 * | estado | lo que NO puede decir |
 * |---|---|
 * | todavía no se buscó | «sin coincidencias» |
 * | la búsqueda falló | «sin coincidencias» |
 * | el grupo vino cortado | que eso es todo lo que hay |
 *
 * Y que la advertencia de que **no se busca dentro de los archivos** llegue
 * hasta la pantalla: sin ella, quien busque una frase que está en el PDF de un
 * procedimiento concluye que ese procedimiento no la menciona.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react';
import type { ReactNode } from 'react';
import { usarBusqueda } from './usar-busqueda';
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

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return { ...real, api: { ...real.api, get: (...a: unknown[]) => get(...a) } };
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

const RESPUESTA = {
  grupos: [
    {
      tipo: 'legal_norm',
      hay_mas: true,
      coincidencias: [
        {
          tipo: 'legal_norm',
          id: 'n-1',
          titulo: 'ESTABLECE NORMA DE EMISIÓN DE RUIDOS',
          codigo: '38',
          contexto: {},
        },
      ],
    },
  ],
  advertencias: ['No se busca dentro del contenido de los archivos adjuntos.'],
};

function responder(respuesta: unknown) {
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('/buscar/')) {
      return respuesta instanceof Error
        ? Promise.reject(respuesta)
        : Promise.resolve(respuesta);
    }
    if (ruta.startsWith('/users/')) return Promise.resolve(mockUsers);
    if (ruta.startsWith('/tenants/')) return Promise.reject(new Error('401'));
    return Promise.resolve([]);
  });
}

function montar() {
  return renderHook(() => usarBusqueda(), { wrapper: envoltura });
}

beforeEach(() => {
  vi.clearAllMocks();
  iniciarSesionComo('admin_empresa');
});

describe('antes de buscar', () => {
  it('no hay lista, y eso no es «sin coincidencias»', () => {
    responder(RESPUESTA);
    const { result } = montar();

    // La pantalla arranca sin resultados y eso significa que nadie preguntó
    // nada todavía, no que no haya nada.
    expect(result.current.grupos).toBeNull();
    expect(result.current.error).toBeNull();
  });
});

describe('al buscar', () => {
  it('manda el término y trae los grupos con su corte', async () => {
    responder(RESPUESTA);
    const { result } = montar();

    await act(async () => {
      await result.current.buscar('emision');
    });

    await waitFor(() => expect(result.current.grupos).not.toBeNull());
    const ruta = String(get.mock.calls.find((c) => String(c[0]).includes('/buscar/'))?.[0]);
    expect(ruta).toContain('q=emision');

    const [grupo] = result.current.grupos!;
    expect(grupo.tipo).toBe('legal_norm');
    expect(grupo.coincidencias[0].codigo).toBe('38');
    // El corte se conserva: sin esto la lista afirma que eso es todo.
    expect(grupo.hayMas).toBe(true);
  });

  it('la advertencia de que no mira dentro de los archivos llega a la pantalla', async () => {
    responder(RESPUESTA);
    const { result } = montar();

    await act(async () => {
      await result.current.buscar('emision');
    });

    expect(result.current.advertencias.join(' ')).toContain('archivos');
  });
});

describe('cuando falla', () => {
  it('lo dice, y NO deja una lista vacía en su lugar', async () => {
    // Es la parte que importa: vaciar la lista haría que un fallo se viera
    // igual que «no hay coincidencias», que es justo lo que el buscador no
    // puede afirmar cuando no pudo preguntar.
    responder(RESPUESTA);
    const { result } = montar();
    await act(async () => {
      await result.current.buscar('emision');
    });
    expect(result.current.grupos).toHaveLength(1);

    responder(new Error('se cayó'));
    await act(async () => {
      await result.current.buscar('otra cosa');
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.grupos).toHaveLength(1);
  });
});
