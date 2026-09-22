/**
 * La cartera del Gestor y sus contratos (RF-65, RF-66, bloque C).
 *
 * ## Que estaba desconectado, medido el 10-sep
 *
 * `gestores-store` decia que la sub-tenancy no estaba implementada y que **no
 * habia endpoint que listara sub-tenants**. Era cierto cuando se escribio, y
 * dejo de serlo al cerrar el bloque C: `GET /gestor/clientes` devuelve la
 * cartera real. La nota se quedo vieja y con ella dos cosas:
 *
 * | | antes | ahora |
 * |---|---|---|
 * | La cartera | `useState([])` fijo, nunca se pedia | sale de `/gestor/clientes` |
 * | `addContrato` | solo memoria: se perdia al recargar | `POST /contracts/` |
 *
 * Es el mismo patron que `addNorm` en la matriz legal: el trabajo estaba hecho
 * del lado de la API y nadie volvio a mirar el comentario que lo bloqueaba.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { GestoresProvider, useGestores } from './gestores-store';
import { AuditLogProvider } from './audit-log-store';
import { ToastProvider } from './toast-store';
import { SessionProvider } from './session';
import { UsersProvider } from './users-store';
import { ApiError } from './api-client';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/gestores',
}));

const get = vi.fn();
const post = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      post: (...a: unknown[]) => post(...a),
      patch: vi.fn(),
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
            <GestoresProvider>{children}</GestoresProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

const CLIENTE = 'c0000000-0000-0000-0000-000000000001';
const CONTRATO = 'd0000000-0000-0000-0000-000000000001';

const clienteApi = (extra: Record<string, unknown> = {}) => ({
  tenant_id: CLIENTE,
  legal_name: 'Minera Andes SpA',
  rut: '76.123.456-7',
  contract_id: CONTRATO,
  contract_number: 'ECOG-2026-001',
  contract_status: 'active',
  start_date: '2026-01-01',
  end_date: '2026-12-31',
  puede_actuar: true,
  ...extra,
});

function responder(clientes: Record<string, unknown>[] = [clienteApi()]) {
  get.mockImplementation((ruta: string) => {
    if (ruta === '/gestor/clientes') return Promise.resolve(clientes);
    if (ruta === '/contracts/') return Promise.resolve([]);
    return Promise.resolve([]);
  });
}

async function montar(clientes?: Record<string, unknown>[]) {
  iniciarSesionComo('admin_empresa');
  responder(clientes);
  const r = renderHook(() => useGestores(), { wrapper });
  await waitFor(() => expect(r.result.current.loading).toBe(false));
  return r;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('la cartera de clientes', () => {
  it('sale de la API y no de una lista fija', async () => {
    const { result } = await montar();
    await waitFor(() => expect(result.current.subTenants).toHaveLength(1));

    expect(get).toHaveBeenCalledWith('/gestor/clientes', expect.anything());
    expect(result.current.subTenants[0]!.nombre).toBe('Minera Andes SpA');
    expect(result.current.subTenants[0]!.rut).toBe('76.123.456-7');
  });

  it('`puede_actuar` decide el estado, y lo resuelve el servidor', async () => {
    // Repetir el criterio —contrato `active` Y dentro de sus fechas— en el
    // navegador seria la tercera copia de una regla que ya vive en un lugar.
    const { result } = await montar([
      clienteApi({ puede_actuar: false, contract_status: 'expired' }),
    ]);
    await waitFor(() => expect(result.current.subTenants).toHaveLength(1));
    expect(result.current.subTenants[0]!.estado).toBe('inactivo');
  });

  it('el cliente sin RUT lo dice, no deja la celda vacia', async () => {
    // Una celda en blanco se lee como "esta empresa no tiene RUT".
    const { result } = await montar([clienteApi({ rut: null })]);
    await waitFor(() => expect(result.current.subTenants).toHaveLength(1));
    expect(result.current.subTenants[0]!.rut).toBe('Sin RUT registrado');
  });

  it('un 403 no deja la pantalla en rojo: es la respuesta a "no eres gestor"', async () => {
    iniciarSesionComo('admin_empresa');
    get.mockImplementation((ruta: string) => {
      if (ruta === '/gestor/clientes') {
        return Promise.reject(new ApiError(403, 'Forbidden', { detail: 'no es un gestor' }));
      }
      return Promise.resolve([]);
    });
    const { result } = renderHook(() => useGestores(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.subTenants).toEqual([]);
    expect(result.current.errorDeCarga).toBeNull();
  });
});

describe('registrar un contrato', () => {
  const alta = {
    subTenantId: CLIENTE,
    numero: 'ECOG-2026-002',
    nombre: 'Asesoria ambiental 2026',
    fechaInicio: '2026-03-01',
    fechaTermino: '2026-12-31',
    camposCustom: { responsable: 'J. Perez' },
  };

  it('llega a la base y no solo a la pantalla', async () => {
    const { result } = await montar();
    post.mockResolvedValue({
      id: 'nuevo',
      client_tenant_id: CLIENTE,
      title: alta.nombre,
      contract_number: alta.numero,
      start_date: '2026-03-01',
      end_date: '2026-12-31',
      scope: alta.camposCustom,
    });

    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.addContrato(alta);
    });

    expect(ok).toBe(true);
    expect(post).toHaveBeenCalledWith(
      '/contracts/',
      expect.objectContaining({
        client_tenant_id: CLIENTE,
        contract_number: 'ECOG-2026-002',
        title: 'Asesoria ambiental 2026',
        scope: { responsable: 'J. Perez' },
      }),
      expect.anything(),
    );
    expect(result.current.contratos.some((c) => c.id === 'nuevo')).toBe(true);
  });

  it('manda fechas de calendario, no marcas de tiempo', async () => {
    // `new Date('2026-03-01').toISOString()` es medianoche UTC, y en Chile eso
    // es el 29 de febrero: la vigencia del contrato empezaria un dia antes.
    const { result } = await montar();
    post.mockResolvedValue({ id: 'nuevo' });

    await act(async () => {
      await result.current.addContrato(alta);
    });

    const cuerpo = post.mock.calls[0]![1] as Record<string, unknown>;
    expect(cuerpo.start_date).toBe('2026-03-01');
    expect(cuerpo.end_date).toBe('2026-12-31');
    expect(String(cuerpo.start_date)).not.toContain('T');
  });

  it('si la API lo rechaza, el contrato NO aparece en la lista', async () => {
    // El numero duplicado es un rechazo esperable: la restriccion es
    // UNIQUE (manager_tenant_id, contract_number).
    const { result } = await montar();
    post.mockRejectedValue(
      new ApiError(409, 'Conflict', { detail: 'ya existe un contrato con ese numero' }),
    );
    const antes = result.current.contratos.length;

    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.addContrato(alta);
    });

    expect(ok).toBe(false);
    expect(result.current.contratos).toHaveLength(antes);
    expect(result.current.errorAlGuardar).toBeTruthy();
  });
});
