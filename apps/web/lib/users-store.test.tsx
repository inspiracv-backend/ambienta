import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { UsersProvider, useUsers } from './users-store';
import { AuditLogProvider } from './audit-log-store';
import { ToastProvider } from './toast-store';
import { SessionProvider } from './session';

/**
 * **Lo que sale a la API, no lo que queda en pantalla.**
 *
 * Este archivo no existía, y por eso tres escrituras de usuarios estuvieron
 * rotas sin que nada lo dijera. Las tres fallaban en silencio y de dos formas
 * distintas:
 *
 * - `inviteUser` mandaba `display_name`, y la API exige `full_name`. Eso es un
 *   **422**: la invitación se veía hecha y no creaba a nadie.
 * - `updateNombre` mandaba `display_name` en un `PATCH`. Eso es peor: Pydantic
 *   descarta los campos que no declara y el `UPDATE` sale vacío, así que la API
 *   responde **200 sin cambiar nada**. Nadie revierte y nadie se entera hasta
 *   recargar.
 * - `updateRole` mandaba `user_type`, que tampoco está en `UserUpdate` —y que
 *   además no es donde viven los permisos.
 *
 * Las pruebas de abajo afirman sobre el **cuerpo** de la llamada. Comprobar que
 * el estado local cambió las habría dejado pasar a las tres.
 */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/usuarios',
}));

const post = vi.fn();
const patch = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: vi.fn().mockResolvedValue([]),
      post: (...a: unknown[]) => post(...a),
      patch: (...a: unknown[]) => patch(...a),
      delete: vi.fn(),
    },
  };
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuditLogProvider>
        {/*
          `UsersProvider` va **por fuera** de `SessionProvider`: la sesión llama
          a `useUsers()` internamente, así que al revés revienta antes de llegar
          a la prueba. Es el mismo orden que usa `tenants-store.test.tsx`.
        */}
        <UsersProvider>
          <SessionProvider>{children}</SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

const TENANT = 'a0000000-0000-0000-0000-000000000001';

beforeEach(() => {
  post.mockReset();
  patch.mockReset();
  post.mockResolvedValue({});
  patch.mockResolvedValue({});
});

describe('invitar a una persona', () => {
  it('manda full_name, que es lo que la API exige', () => {
    const { result } = renderHook(() => useUsers(), { wrapper });

    act(() => {
      result.current.inviteUser({
        tenantId: TENANT,
        nombre: 'Carolina Pérez',
        email: 'carolina@ejemplo.cl',
        role: 'usuario_interno',
        plantIds: [],
        departamentoId: null,
      });
    });

    const [ruta, cuerpo, opciones] = post.mock.calls.at(-1)!;
    expect(ruta).toBe('/users/');
    // `full_name` es obligatorio en `UserCreate`. Con `display_name` la
    // respuesta era 422 y la persona nunca se creaba.
    expect(cuerpo).toMatchObject({ full_name: 'Carolina Pérez' });
    expect(cuerpo).not.toHaveProperty('display_name');
    expect(opciones).toEqual({ tenantId: TENANT });
  });
});

describe('cambiar el nombre', () => {
  it('manda full_name y no display_name', () => {
    const { result } = renderHook(() => useUsers(), { wrapper });
    const alguien = result.current.users.find((u) => u.tenantId);
    expect(alguien, 'el mock de usuarios no trae a nadie con empresa').toBeTruthy();

    act(() => {
      result.current.updateNombre(alguien!.id, 'Nombre Nuevo');
    });

    const [ruta, cuerpo, opciones] = patch.mock.calls.at(-1)!;
    expect(ruta).toBe(`/users/${alguien!.id}`);
    expect(cuerpo).toEqual({ full_name: 'Nombre Nuevo' });
    expect(opciones).toEqual({ tenantId: alguien!.tenantId });
  });
});

describe('cambiar el rol', () => {
  it('NO escribe a la API, y lo dice', () => {
    /**
     * **Esto fija una limitación, no una funcionalidad.**
     *
     * Antes mandaba `user_type` y recibía un 200 que no cambiaba nada. El
     * arreglo no es renombrar el campo: `users.user_type` es una etiqueta y
     * **los permisos salen de `user_roles`**, otra tabla con su propia
     * vigencia. Escribir la etiqueta cambiaría la ficha sin cambiar lo que la
     * persona puede hacer.
     *
     * Cuando #140 conecte el rol contra `user_roles`, esta prueba debe fallar y
     * reescribirse.
     */
    const { result } = renderHook(() => useUsers(), { wrapper });
    const alguien = result.current.users.find((u) => u.tenantId);

    act(() => {
      result.current.updateRole(alguien!.id, 'admin_empresa');
    });

    expect(patch).not.toHaveBeenCalled();
  });
});
