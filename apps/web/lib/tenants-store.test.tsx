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
const post = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      patch: (...a: unknown[]) => patch(...a),
      post: (...a: unknown[]) => post(...a),
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
  post.mockResolvedValue({});
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

describe('el alta de empresa manda el perfil normativo', () => {
  /** Lo mínimo que exige `createTenant`, con el perfil normativo puesto. */
  const NUEVA = {
    nombre: 'Forestal Nueva',
    pais: 'CL' as const,
    numeroIdentificacion: '77.000.111-2',
    sector: 'Industria manufacturera',
    sectorId: 3,
    tramo: 'mediana' as const,
    certificaciones: [],
    esGestor: false,
    plan: 'contrato' as const,
    diasVigencia: 365,
    limiteUsuarios: 10,
    modulosActivos: [],
  };

  it('el sector y el tramo llegan a la API', async () => {
    // Sin esto la empresa se crea, se ve bien, y su matriz responde
    // `sin_perfil` para siempre sin que nadie entienda por qué.
    const { result } = await montar({});

    act(() => void result.current.t.createTenant(NUEVA));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [ruta, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(ruta).toBe('/tenants/');
    expect(cuerpo.sector_id).toBe(3);
    expect(cuerpo.size_bracket).toBe('mediana');
  });

  it('sin sector manda null, no lo omite', async () => {
    // Omitir la clave y mandar `null` se leen distinto en el otro lado: uno
    // dice "no toqué esto", el otro "no tiene sector".
    const { result } = await montar({});

    act(() => void result.current.t.createTenant({ ...NUEVA, sectorId: undefined, tramo: undefined }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(cuerpo).toHaveProperty('sector_id', null);
    expect(cuerpo).toHaveProperty('size_bracket', null);
  });

  it('reemplaza el id inventado por el que devuelve la API', async () => {
    // El id local es `tenant-${Date.now()}`. Si no se reconcilia, la empresa
    // recién creada queda en pantalla apuntando a una fila que no existe, y
    // cualquier acción posterior sobre ella falla sin explicación.
    const REAL = 'b0000000-0000-0000-0000-0000000000ff';
    post.mockResolvedValue({
      id: REAL,
      legal_name: 'Forestal Nueva',
      rut_tax_id: '77.000.111-2',
      business_activity: 'Industria manufacturera',
      sector_id: 3,
      size_bracket: 'mediana',
      status: 'active',
      tenant_type: 'company',
      created_at: '2026-08-19T00:00:00Z',
    });
    const { result } = await montar({});

    act(() => void result.current.t.createTenant(NUEVA));

    await waitFor(() => expect(result.current.t.tenants).toHaveLength(2));
    await waitFor(() => {
      const creada = result.current.t.tenants.find((t) => t.nombre === 'Forestal Nueva');
      expect(creada?.id).toBe(REAL);
    });
    const creada = result.current.t.tenants.find((t) => t.id === REAL);
    expect(creada?.sectorId).toBe(3);
    expect(creada?.tramo).toBe('mediana');
  });

  it('si la API rechaza el alta, la empresa desaparece y lo dice', async () => {
    // Antes era `.catch(() => {})`: quedaba en la lista como si existiera y se
    // esfumaba al recargar. Es el mismo silencio que escondió que el alta de no
    // conformidades nunca había funcionado.
    post.mockRejectedValue(
      new ApiError(422, 'Unprocessable Entity', { detail: 'RUT ya registrado' }),
    );
    const { result } = await montar({});

    act(() => void result.current.t.createTenant(NUEVA));

    await waitFor(() => expect(result.current.toast.toasts.length).toBeGreaterThan(0));
    expect(result.current.t.tenants.some((t) => t.nombre === 'Forestal Nueva')).toBe(false);
    expect(result.current.toast.toasts[0].mensaje).toContain('No se pudo crear');
    // El motivo tiene que llegar: "algo salió mal" no le sirve a nadie.
    expect(result.current.toast.toasts[0].descripcion).toContain('RUT ya registrado');
  });
});

describe('el perfil normativo da la vuelta completa', () => {
  it('lee el sector y el tramo que devuelve la API', async () => {
    // El otro lado del viaje. Mandarlos sin leerlos daría un "guardado" que se
    // deshace al recargar — el error que ya costó `limiteUsuarios`.
    get.mockImplementation((ruta: string) =>
      Promise.resolve(
        ruta.startsWith('/tenants')
          ? [{ ...tenantApi({}), sector_id: 5, size_bracket: 'grande' }]
          : [],
      ),
    );
    const r = renderHook(() => ({ t: useTenants(), toast: useToast() }), { wrapper });
    await waitFor(() => expect(r.result.current.t.tenants).toHaveLength(1));

    expect(r.result.current.t.tenants[0].sectorId).toBe(5);
    expect(r.result.current.t.tenants[0].tramo).toBe('grande');
  });

  it('una empresa antigua sin perfil no inventa uno', async () => {
    // `undefined` es lo que hace que la matriz responda `sin_perfil` en vez de
    // proponer normativa que nadie eligió. Rellenarlo con un valor por defecto
    // sería peor que dejarlo vacío.
    const { result } = await montar({});

    expect(result.current.t.tenants[0].sectorId).toBeUndefined();
    expect(result.current.t.tenants[0].tramo).toBeUndefined();
  });

  it('un tramo que la base no acepta se lee como ausente', async () => {
    get.mockImplementation((ruta: string) =>
      Promise.resolve(
        ruta.startsWith('/tenants') ? [{ ...tenantApi({}), size_bracket: 'enorme' }] : [],
      ),
    );
    const r = renderHook(() => ({ t: useTenants(), toast: useToast() }), { wrapper });
    await waitFor(() => expect(r.result.current.t.tenants).toHaveLength(1));

    expect(r.result.current.t.tenants[0].tramo).toBeUndefined();
  });
});
