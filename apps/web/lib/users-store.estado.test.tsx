/**
 * Activar y desactivar a una persona, y decir la verdad sobre si funciono
 * (#141, RF-08).
 *
 * ## Lo que estaba roto, y por que no se notaba
 *
 * `setEstado` mandaba `status: 'inactive'`. Ese valor **no existe**: el CHECK
 * de `users` admite `invited`, `active`, `blocked` y `disabled`. Postgres
 * rechazaba la fila siempre, asi que desactivar a una persona **no llegaba
 * nunca a la base**.
 *
 * Y no se notaba porque el error se tapaba a si mismo tres veces:
 *
 * 1. `.catch(() => {})` se comia el rechazo.
 * 2. La pantalla ya habia pintado el cambio de forma optimista.
 * 3. El aviso decia "el cambio quedo registrado en el historial" **sin mirar
 *    la respuesta**, asi que afirmaba algo que la base no tenia.
 *
 * Recargar deshacia todo, y ahi la persona desactivada volvia — ademas
 * mostrada como **"Invitada"**, porque el mapeo de vuelta trataba cualquier
 * estado distinto de `active` como una invitacion pendiente. Dos situaciones
 * opuestas con el mismo aspecto: la segunda invita a reenviarle la invitacion
 * a quien acaba de ser dado de baja.
 *
 * Estas pruebas afirman sobre **lo que se manda** y **lo que queda en pantalla
 * despues de la respuesta**, que es donde vivia el error.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import type { ReactNode } from 'react';
import { ApiError } from './api-client';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider, useUsers } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();
const patch = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      patch: (...a: unknown[]) => patch(...a),
      post: vi.fn(),
      delete: vi.fn(),
    },
  };
});

const TENANT = 'a0000000-0000-0000-0000-000000000001';

/** Una persona activa de la empresa, como la devuelve la API. */
const ACTIVA = {
  id: 'u-1',
  tenant_id: TENANT,
  full_name: 'Paula Rivas',
  email: 'paula@ejemplo.cl',
  user_type: 'internal',
  status: 'active',
};

function envoltura({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>{children}</SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

function montar() {
  return renderHook(() => useUsers(), { wrapper: envoltura });
}

beforeEach(() => {
  window.localStorage.clear();
  get.mockReset();
  patch.mockReset();
  iniciarSesionComo('admin_empresa');
  responder({ ...ACTIVA });
  patch.mockResolvedValue({ ...ACTIVA, status: 'disabled' });
});

/**
 * Se enruta por ruta y no con un `mockResolvedValue` unico.
 *
 * Sin Clerk el store enumera `/tenants/` y despues pide `/users/` por cada uno
 * (ver el efecto de `UsersProvider`), asi que una respuesta unica alimentaria
 * las dos llamadas con la misma lista. Es la trampa que ya documenta
 * `stores-sin-datos.test.tsx`: el fallo aparece lejos de su causa.
 */
function responder(usuario: Record<string, unknown>) {
  get.mockImplementation((ruta: string) => {
    if (ruta.startsWith('/tenants')) return Promise.resolve([{ id: TENANT }]);
    if (ruta.startsWith('/users')) return Promise.resolve([usuario]);
    return Promise.resolve([]);
  });
}

describe('lo que se le manda a la API', () => {
  it('desactivar manda `disabled`, un estado que la base ACEPTA', async () => {
    // `inactive` no esta en el CHECK de `users`: Postgres rechazaba la fila
    // siempre, y desactivar a alguien no llegaba nunca a la base.
    const { result } = montar();
    await waitFor(() => expect(result.current.users.some((u) => u.id === 'u-1')).toBe(true));

    await act(async () => {
      await result.current.setEstado('u-1', 'desactivado');
    });

    expect(patch).toHaveBeenCalledTimes(1);
    expect(patch.mock.calls[0][0]).toBe('/users/u-1');
    expect(patch.mock.calls[0][1]).toEqual({ status: 'disabled' });
    expect(patch.mock.calls[0][1].status).not.toBe('inactive');
  });

  it('reactivar manda `active`, no `invited`', async () => {
    // Devolver a alguien a "invitada" le pediria aceptar de nuevo una
    // invitacion que ya acepto en su momento.
    const { result } = montar();
    await waitFor(() => expect(result.current.users.some((u) => u.id === 'u-1')).toBe(true));

    await act(async () => {
      await result.current.setEstado('u-1', 'activo');
    });

    expect(patch.mock.calls[0][1]).toEqual({ status: 'active' });
  });
});

describe('lo que se lee de la API', () => {
  it('una persona DESACTIVADA no se muestra como invitada', async () => {
    // Son situaciones opuestas: una fue dada de baja, la otra no ha aceptado.
    // Confundirlas invita a reenviarle la invitacion a quien acaba de salir.
    responder({ ...ACTIVA, status: 'disabled' });
    const { result } = montar();

    await waitFor(() => {
      const u = result.current.users.find((x) => x.id === 'u-1');
      expect(u?.estado).toBe('desactivado');
    });
  });

  it('`blocked` tambien es desactivado', async () => {
    responder({ ...ACTIVA, status: 'blocked' });
    const { result } = montar();

    await waitFor(() => {
      expect(result.current.users.find((x) => x.id === 'u-1')?.estado).toBe('desactivado');
    });
  });

  it('`invited` sigue siendo invitado', async () => {
    // Y esto es lo que impide "arreglar" el mapeo mandando todo a desactivado.
    responder({ ...ACTIVA, status: 'invited' });
    const { result } = montar();

    await waitFor(() => {
      expect(result.current.users.find((x) => x.id === 'u-1')?.estado).toBe('invitado');
    });
  });
});

describe('cuando el servidor rechaza', () => {
  it('la persona vuelve a su estado anterior en pantalla', async () => {
    // Es el caso del 409 de #141: desactivar a la ultima persona que puede
    // administrar usuarios. Dejarla pintada como desactivada seria la pantalla
    // afirmando algo que la base no tiene.
    const { result } = montar();
    await waitFor(() => expect(result.current.users.some((u) => u.id === 'u-1')).toBe(true));
    patch.mockRejectedValue(
      new ApiError(409, 'Conflict', { detail: 'es la unica persona que puede administrar' }),
    );

    await act(async () => {
      await result.current.setEstado('u-1', 'desactivado');
    });

    expect(result.current.users.find((u) => u.id === 'u-1')?.estado).toBe('activo');
  });

  it('se devuelve el motivo del servidor, no uno generico', async () => {
    const { result } = montar();
    await waitFor(() => expect(result.current.users.some((u) => u.id === 'u-1')).toBe(true));
    patch.mockRejectedValue(
      new ApiError(409, 'Conflict', {
        detail: 'Paula Rivas es la unica persona activa que puede administrar usuarios.',
      }),
    );

    let r: { ok: boolean; error?: string } = { ok: true };
    await act(async () => {
      r = await result.current.setEstado('u-1', 'desactivado');
    });

    expect(r.ok).toBe(false);
    expect(r.error).toContain('unica persona activa que puede administrar');
  });

  it('cuando funciona, se informa que funciono', async () => {
    // La otra mitad: una funcion que siempre devuelve `ok: false` tampoco
    // sirve, y las pruebas de arriba no lo distinguirian solas.
    const { result } = montar();
    await waitFor(() => expect(result.current.users.some((u) => u.id === 'u-1')).toBe(true));

    let r: { ok: boolean; error?: string } = { ok: false };
    await act(async () => {
      r = await result.current.setEstado('u-1', 'desactivado');
    });

    expect(r.ok).toBe(true);
    expect(result.current.users.find((u) => u.id === 'u-1')?.estado).toBe('desactivado');
  });
});
