import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { UsersProvider, cuerpoDeInvitacion, useUsers } from './users-store';
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
 *   **422**: la invitación se veía hecha y no creaba a nadie. Y arreglado eso,
 *   seguía sin pedirle la invitación a Clerk: la persona no recibía correo.
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
const put = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: vi.fn().mockResolvedValue([]),
      post: (...a: unknown[]) => post(...a),
      patch: (...a: unknown[]) => patch(...a),
      put: (...a: unknown[]) => put(...a),
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
  const INVITACION = {
    tenantId: TENANT,
    nombre: 'Carolina Pérez',
    email: 'carolina@ejemplo.cl',
    role: 'usuario_interno' as const,
    departamentoId: 'd0000000-0000-0000-0000-000000000001',
  };

  it('pide la invitación a /users/invitaciones, con su rol', async () => {
    // Antes solo hacía `POST /users/`: la fila quedaba "Invitada" y **nadie le
    // pedía la invitación a Clerk**, así que la persona nunca recibía el correo.
    post.mockResolvedValue({
      user: {
        id: 'u0000000-0000-0000-0000-0000000000aa',
        tenant_id: TENANT,
        full_name: 'Carolina Pérez',
        email: 'carolina@ejemplo.cl',
        user_type: 'internal',
        status: 'invited',
        department_id: INVITACION.departamentoId,
      },
      clerk_invitation_id: 'inv_1',
    });
    const { result } = renderHook(() => useUsers(), { wrapper });

    let creado: Awaited<ReturnType<typeof result.current.inviteUser>> | undefined;
    await act(async () => {
      creado = await result.current.inviteUser(INVITACION);
    });

    const [ruta, cuerpo, opciones] = post.mock.calls.at(-1)!;
    expect(ruta).toBe('/users/invitaciones');
    // `role_code` es obligatorio: sin rol la persona entra y recibe 403 en todo.
    expect(cuerpo).toEqual({
      full_name: 'Carolina Pérez',
      email: 'carolina@ejemplo.cl',
      user_type: 'internal',
      department_id: INVITACION.departamentoId,
      role_code: 'encargado_ambiental',
    });
    expect(opciones).toEqual({ tenantId: TENANT });
    expect(creado?.estado).toBe('invitado');
    expect(result.current.users.some((u) => u.id === 'u0000000-0000-0000-0000-0000000000aa')).toBe(true);
  });

  it('el administrador va sin departamento y con admin_empresa', () => {
    expect(cuerpoDeInvitacion({ ...INVITACION, role: 'admin_empresa', departamentoId: null })).toMatchObject({
      user_type: 'tenant_admin',
      department_id: null,
      role_code: 'admin_empresa',
    });
  });

  it('si la API rechaza, rechaza y NO deja a nadie en la lista', async () => {
    // La fila optimista con id inventado se veía "Invitada" aunque la API
    // hubiera dicho que no.
    post.mockRejectedValue(new Error('Falta CLERK_SECRET_KEY'));
    const { result } = renderHook(() => useUsers(), { wrapper });
    const antes = result.current.users.length;

    await act(async () => {
      await expect(result.current.inviteUser(INVITACION)).rejects.toThrow('CLERK_SECRET_KEY');
    });

    expect(result.current.users).toHaveLength(antes);
    expect(result.current.users.some((u) => u.email === 'carolina@ejemplo.cl')).toBe(false);
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

describe('alcance por planta (#25)', () => {
  it('manda la planta al endpoint de alcance y adopta lo que la base dejó', async () => {
    put.mockResolvedValue({ user_id: 'u-1', facility_ids: ['f-1'] });
    const { result } = renderHook(() => useUsers(), { wrapper });

    let despues: string[] = [];
    await act(async () => {
      despues = await result.current.fijarAlcance('u-1', TENANT, 'f-1');
    });

    const [ruta, cuerpo, opciones] = put.mock.calls.at(-1)!;
    expect(ruta).toBe('/users/u-1/alcance');
    expect(cuerpo).toEqual({ facility_id: 'f-1' });
    expect(opciones).toEqual({ tenantId: TENANT });
    expect(despues).toEqual(['f-1']);
  });

  it('"todas las plantas" se manda como null explícito, no omitiendo el campo', async () => {
    put.mockResolvedValue({ user_id: 'u-1', facility_ids: [] });
    const { result } = renderHook(() => useUsers(), { wrapper });
    await act(async () => {
      await result.current.fijarAlcance('u-1', TENANT, null);
    });
    // La API exige el campo: un cuerpo vacío no puede ampliar el acceso.
    expect(put.mock.calls.at(-1)![1]).toEqual({ facility_id: null });
  });

  it('si la base lo rechaza, rechaza', async () => {
    put.mockRejectedValue(new Error('409'));
    const { result } = renderHook(() => useUsers(), { wrapper });
    await act(async () => {
      await expect(result.current.fijarAlcance('u-1', TENANT, 'f-1')).rejects.toThrow('409');
    });
  });
});
