import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { TenantsProvider, useTenants } from './tenants-store';
import { AuditLogProvider } from './audit-log-store';
import { ToastProvider, useToast } from './toast-store';
import { SessionProvider } from './session';
import { UsersProvider } from './users-store';
import { ApiError } from './api-client';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/gestion-tenants',
}));

vi.mock('@/mocks/tenants', () => ({ mockTenants: [] }));

const get = vi.fn();
const patch = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      patch: (...a: unknown[]) => patch(...a),
      post: vi.fn(() => Promise.resolve({})),
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
            <TenantsProvider>{children}</TenantsProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

const TENANT = 'a0000000-0000-0000-0000-000000000001';

/** Un tenant como lo devuelve la API, con lo suyo dentro de `settings`. */
function tenantApi(settings: Record<string, unknown> | undefined) {
  return {
    id: TENANT,
    legal_name: 'Minera Ejemplo',
    rut_tax_id: '76.111.222-3',
    business_activity: 'Mineria',
    status: 'active',
    tenant_type: 'company',
    created_at: '2026-01-01T00:00:00Z',
    ...(settings === undefined ? {} : { settings }),
  };
}

async function montar(settings: Record<string, unknown> | undefined) {
  get.mockImplementation((ruta: string) =>
    Promise.resolve(ruta.startsWith('/tenants') ? [tenantApi(settings)] : []),
  );
  const r = renderHook(() => ({ t: useTenants(), toast: useToast() }), { wrapper });
  await waitFor(() => expect(r.result.current.t.loading).toBe(false));
  await waitFor(() => expect(r.result.current.t.tenants).toHaveLength(1));
  return r;
}

beforeEach(() => {
  vi.clearAllMocks();
  patch.mockResolvedValue({});
  window.localStorage.clear();
});

describe('los campos de settings dan la vuelta completa', () => {
  it('lee el limite de usuarios de settings, no de un valor fijo', async () => {
    const { result } = await montar({ limiteUsuarios: 250 });

    // Antes esto devolvia 50 escrito a mano, sin importar lo que hubiera guardado.
    expect(result.current.t.tenants[0].suscripcion.limiteUsuarios).toBe(250);
  });

  it('lee los modulos activos de settings', async () => {
    const { result } = await montar({ modulosActivos: ['auditorias'] });
    expect(result.current.t.tenants[0].modulosActivos).toEqual(['auditorias']);
  });

  it('un tenant sin settings sigue cargando con los valores por defecto', async () => {
    // Lo que pasa con las empresas creadas antes de que existiera este campo.
    const { result } = await montar(undefined);

    expect(result.current.t.tenants[0].suscripcion.limiteUsuarios).toBe(50);
    expect(result.current.t.tenants[0].modulosActivos).toEqual([]);
  });

  it('guarda el limite sin borrar las otras claves de settings', async () => {
    // `settings` lo comparten varias pantallas: mandar solo la clave propia
    // borraria lo que escribieron las demas, y solo se veria al recargar otra.
    const { result } = await montar({ limiteUsuarios: 50, modulosActivos: ['auditorias'] });

    act(() => result.current.t.setLimiteUsuarios(TENANT, 120));

    await waitFor(() => expect(patch).toHaveBeenCalled());
    const [, cuerpo] = patch.mock.calls[0] as [string, { settings: Record<string, unknown> }];

    expect(cuerpo.settings.limiteUsuarios).toBe(120);
    expect(cuerpo.settings.modulosActivos).toEqual(['auditorias']);
  });

  it('revierte y avisa cuando la API rechaza el cambio', async () => {
    const { result } = await montar({ limiteUsuarios: 50 });
    patch.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'limite invalido' }));

    act(() => result.current.t.setLimiteUsuarios(TENANT, 999));
    expect(result.current.t.tenants[0].suscripcion.limiteUsuarios).toBe(999);

    // Vuelve al valor anterior: dejar el 999 en pantalla afirmaria algo falso.
    await waitFor(() => expect(result.current.t.tenants[0].suscripcion.limiteUsuarios).toBe(50));

    expect(result.current.toast.toasts[0].tipo).toBe('error');
    expect(result.current.toast.toasts[0].descripcion).toBe('limite invalido');
  });

  it('guarda el logo, que antes no se leia en absoluto', async () => {
    const { result } = await montar({ logoUrl: 'https://ejemplo.cl/a.png' });
    expect(result.current.t.tenants[0].logoUrl).toBe('https://ejemplo.cl/a.png');

    act(() => result.current.t.updateLogo(TENANT, 'https://ejemplo.cl/b.png'));

    await waitFor(() => expect(patch).toHaveBeenCalled());
    const [, cuerpo] = patch.mock.calls[0] as [string, { settings: Record<string, unknown> }];
    expect(cuerpo.settings.logoUrl).toBe('https://ejemplo.cl/b.png');
  });
});
