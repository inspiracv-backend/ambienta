/**
 * El centro de notificaciones y su contador (#124).
 *
 * **Este archivo no existía**, y por eso nadie noto que una empresa **sin**
 * notificaciones veia tres inventadas.
 *
 * El store hacia `if (mapped.length > 0) setNotifications(mapped)`, que no
 * distingue dos cosas muy distintas:
 *
 * - la API fallo → quedarse con lo que hay es un respaldo razonable
 * - la API respondio **cero** → quedarse con los datos de ejemplo es mentir
 *
 * Y aca la mentira **mueve la campana**: un badge rojo con un numero falso hace
 * que alguien deje lo que esta haciendo para ir a mirar. Cuando descubre que no
 * habia nada, deja de creerle al badge — y entonces el aviso real pasa de largo.
 *
 * Es el mismo patron que en otros nueve stores. Ver la issue del barrido.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { NotificationsProvider, useNotifications } from './notifications-store';
import { SessionProvider, useSession } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo, usuarioConRol } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/notificaciones',
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

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>
          <NotificationsProvider>{children}</NotificationsProvider>
        </SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

function avisoApi(over: Record<string, unknown> = {}) {
  return {
    id: 'n-1',
    tenant_id: 't-1',
    recipient_user_id: 'u-1',
    subject: 'Vence en 7 dias: Declaración SIDREP',
    body: 'La declaración vence el 03/09/2026.',
    created_at: '2026-08-26T12:00:00Z',
    read_at: null,
    ...over,
  };
}

/** El id del usuario de la sesion de prueba, para que los avisos sean suyos. */
function usuarioId(): string {
  return usuarioConRol('admin_empresa').id;
}

/**
 * Monta el store **y espera a que la sesion este cargada**.
 *
 * `waitFor(loading === false)` a secas no sirve: sin sesion el efecto del store
 * sale temprano y `loading` pasa a `false` de inmediato, asi que las
 * afirmaciones corren contra los datos de ejemplo y **la API ni se llama**.
 * Medido al escribir estas pruebas: `user` llegaba `undefined` y el unico `get`
 * registrado era el de otro provider.
 *
 * Es la misma trampa que ya aparecio en `obligations-store.test.tsx`: esperar
 * una condicion que se cumple sin que pase nada.
 */
async function montar(filas: unknown) {
  const usuario = iniciarSesionComo('admin_empresa');
  // **Se enruta por ruta, no `mockResolvedValue` a secas.** Devolver las
  // notificaciones tambien a `/tenants/` y `/users/` alimenta a los otros
  // providers con datos que no son suyos, y el fallo aparece lejos: la sesion
  // queda a medias y `markAllAsRead` sale sin llamar a nada.
  get.mockImplementation((ruta: string) =>
    Promise.resolve(String(ruta).startsWith('/notifications') ? filas : []),
  );

  const r = renderHook(() => ({ n: useNotifications(), s: useSession() }), { wrapper });

  await waitFor(() => expect(r.result.current.s.user?.tenantId).toBeTruthy());
  await waitFor(() =>
    expect(get.mock.calls.some(([ruta]) => String(ruta).startsWith('/notifications'))).toBe(true),
  );
  await waitFor(() => expect(r.result.current.n.loading).toBe(false));

  return { store: () => r.result.current.n, usuario };
}

beforeEach(() => {
  vi.clearAllMocks();
  patch.mockResolvedValue({});
  window.localStorage.clear();
});

describe('lo que muestra la campana', () => {
  it('una empresa SIN notificaciones no ve ninguna', async () => {
    // **La afirmación central.** Antes veía las tres de ejemplo, con su badge.
    const { store } = await montar([]);

    expect(store().notifications).toHaveLength(0);
  });

  it('con notificaciones reales muestra esas', async () => {
    const { store } = await montar([avisoApi(), avisoApi({ id: 'n-2' })]);

    expect(store().notifications).toHaveLength(2);
    expect(store().notifications[0]!.titulo).toMatch(/Vence en 7 dias/);
  });

  it('una sin leer llega marcada como no leída', async () => {
    // De acá sale el número del badge. `read_at: null` es "no leída".
    const { store } = await montar([avisoApi({ read_at: null })]);

    expect(store().notifications[0]!.leida).toBe(false);
  });

  it('una ya leída llega marcada como leída', async () => {
    const { store } = await montar([avisoApi({ read_at: '2026-08-26T13:00:00Z' })]);

    expect(store().notifications[0]!.leida).toBe(true);
  });
});

describe('cuando la API falla', () => {
  it('NO borra lo que ya se veía', async () => {
    // El otro lado del arreglo: distinguir "cero" de "falló" tiene que servir
    // para las dos cosas. Sin red, una pantalla vacía parece un sistema roto.
    iniciarSesionComo('admin_empresa');
    get.mockRejectedValue(new Error('sin red'));

    const r = renderHook(() => ({ n: useNotifications(), s: useSession() }), { wrapper });
    await waitFor(() => expect(r.result.current.s.user?.tenantId).toBeTruthy());
    await waitFor(() => expect(r.result.current.n.loading).toBe(false));

    expect(r.result.current.n.notifications.length).toBeGreaterThan(0);
  });
});

describe('marcar como leídas', () => {
  it('solo toca las que de verdad estaban sin leer', async () => {
    // Marcar una ya leída movería su `read_at` a hoy y borraría cuándo se leyó
    // en realidad — un dato que no se puede recuperar.
    const { store, usuario } = await montar([
      avisoApi({ id: 'n-1', recipient_user_id: usuarioId(), read_at: null }),
      avisoApi({ id: 'n-2', recipient_user_id: usuarioId(), read_at: '2026-08-20T10:00:00Z' }),
    ]);

    store().markAllAsRead(usuario.id);

    expect(patch).toHaveBeenCalledTimes(1);
    expect(patch.mock.calls[0]![0]).toContain('n-1');
  });

  it('sin ninguna pendiente no llama a la API', async () => {
    const { store, usuario } = await montar([
      avisoApi({ recipient_user_id: usuarioId(), read_at: '2026-08-20T10:00:00Z' }),
    ]);

    store().markAllAsRead(usuario.id);

    expect(patch).not.toHaveBeenCalled();
  });
});
