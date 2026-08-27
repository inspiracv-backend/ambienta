import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { AuditsProvider, useAudits } from './audits-store';
import { AuditLogProvider } from './audit-log-store';
import { ToastProvider, useToast } from './toast-store';
import { SessionProvider } from './session';
import { UsersProvider } from './users-store';
import { ApiError } from './api-client';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/auditorias',
}));

// Sin datos de ejemplo: lo que se mida tiene que venir de la API, no del
// respaldo. Si el store dejara de mapear, la lista quedaria vacia y se nota.
vi.mock('@/mocks/audits', () => ({ mockAudits: [], mockNonConformities: [] }));

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
            <AuditsProvider>{children}</AuditsProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

const NC_ID = 'b0000000-0000-0000-0000-0000000000aa';

/** Una no conformidad tal como la devuelve la API, con sus nombres y valores. */
function ncApi(extra: Record<string, unknown> = {}) {
  return {
    id: NC_ID,
    tenant_id: 'a0000000-0000-0000-0000-000000000001',
    facility_id: 'c0000000-0000-0000-0000-000000000001',
    code: 'NC-2026-001',
    title: 'Derrame en patio',
    description: 'Derrame de aceite sin contencion en el patio de maniobras',
    severity: 'critical',
    status: 'open',
    root_cause_answers: [],
    improvement_stages: {},
    detected_at: '2026-08-01T10:00:00Z',
    owner_user_id: 'd0000000-0000-0000-0000-000000000001',
    closed_at: null,
    ...extra,
  };
}

async function montar(nc: Record<string, unknown>[] = [ncApi()]) {
  iniciarSesionComo('admin_empresa');
  get.mockImplementation((ruta: string) =>
    Promise.resolve(ruta.includes('nonconformities') ? nc : []),
  );
  patch.mockResolvedValue({});
  post.mockResolvedValue(ncApi());
  const r = renderHook(() => ({ a: useAudits(), toast: useToast() }), { wrapper });
  await waitFor(() => expect(r.result.current.a.loading).toBe(false));
  return r;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('lectura de no conformidades', () => {
  it('mapea las que devuelve la API en vez de descartarlas', async () => {
    // La razon de ser de este cambio: el store pedia
    // `/audits/nonconformities/` y tiraba la respuesta, asi que la pantalla
    // mostraba ejemplos con ids que la API no conoce y **ninguna** escritura
    // sobre ellos podia funcionar.
    const { result } = await montar();

    await waitFor(() => expect(result.current.a.nonConformities).toHaveLength(1));
    expect(result.current.a.nonConformities[0]!.id).toBe(NC_ID);
  });

  it('traduce la severidad de la base al vocabulario de la pantalla', async () => {
    const { result } = await montar([ncApi({ severity: 'critical' })]);
    await waitFor(() => expect(result.current.a.nonConformities).toHaveLength(1));
    expect(result.current.a.nonConformities[0]!.criticidad).toBe('alta');
  });

  it('agrupa las tres etapas intermedias en "en tratamiento"', async () => {
    // La base modela seis estados y la pantalla tres. Analisis, plan de accion
    // y verificacion son todas "en tratamiento" para quien mira la lista.
    for (const status of ['analysis', 'action_plan', 'verification']) {
      vi.clearAllMocks();
      const { result } = await montar([ncApi({ status })]);
      await waitFor(() => expect(result.current.a.nonConformities).toHaveLength(1));
      expect(result.current.a.nonConformities[0]!.estado).toBe('en_tratamiento');
    }
  });

  it('no rompe si `root_cause_answers` no viene como lista', async () => {
    // Es una columna JSONB: nada impide que llegue un objeto. Renderizar los
    // 5 porques sobre algo que no es lista rompe la pantalla entera.
    const { result } = await montar([ncApi({ root_cause_answers: {} })]);
    await waitFor(() => expect(result.current.a.nonConformities).toHaveLength(1));
    expect(result.current.a.nonConformities[0]!.cincoPorques).toEqual([]);
  });

  it('deriva el cierre de `closed_at` en vez de inventarlo', async () => {
    const { result } = await montar([
      ncApi({ status: 'closed', closed_at: '2026-08-10T12:00:00Z' }),
    ]);
    await waitFor(() => expect(result.current.a.nonConformities).toHaveLength(1));
    const nc = result.current.a.nonConformities[0]!;
    expect(nc.estado).toBe('cerrada');
    expect(nc.cierre?.fecha).toBe('2026-08-10T12:00:00Z');
  });
});

describe('escritura de los 5 porques', () => {
  it('manda el analisis a la API y no solo al estado local', async () => {
    const { result } = await montar();
    await waitFor(() => expect(result.current.a.nonConformities).toHaveLength(1));

    act(() => result.current.a.updatePorques(NC_ID, ['Sin contencion', 'Sin mantencion']));

    await waitFor(() => expect(patch).toHaveBeenCalled());
    const [ruta, cuerpo] = patch.mock.calls[0]!;
    expect(ruta).toBe(`/audits/nonconformities/${NC_ID}`);
    expect((cuerpo as Record<string, unknown>).root_cause_answers).toEqual([
      'Sin contencion',
      'Sin mantencion',
    ]);
  });

  it('revierte y avisa cuando la API rechaza', async () => {
    // Sin esto la pantalla afirma un cambio que la base nunca recibio, que es
    // el engano que este trabajo existe para sacar.
    const { result } = await montar();
    await waitFor(() => expect(result.current.a.nonConformities).toHaveLength(1));
    patch.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'Valor invalido' }));

    act(() => result.current.a.updatePorques(NC_ID, ['Algo']));

    await waitFor(() => expect(result.current.toast.toasts).toHaveLength(1));
    expect(result.current.toast.toasts[0]!.tipo).toBe('error');
    expect(result.current.a.nonConformities[0]!.cincoPorques).toEqual([]);
  });
});

describe('cierre', () => {
  it('usa el endpoint /close y no un PATCH de estado', async () => {
    /**
     * La base exige `(status='closed') = (closed_at IS NOT NULL)`. Un PATCH que
     * manda solo el estado viola ese CHECK y la fila nunca se cierra. El
     * endpoint dedicado ademas rechaza el cierre si quedan planes de accion
     * abiertos — una regla de negocio que el PATCH suelto se saltaba.
     */
    const { result } = await montar();
    await waitFor(() => expect(result.current.a.nonConformities).toHaveLength(1));

    act(() => result.current.a.closeNonConformity(NC_ID, 'd0000000-0000-0000-0000-000000000001'));

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0]![0]).toBe(`/audits/nonconformities/${NC_ID}/close`);
    expect(patch).not.toHaveBeenCalled();
  });
});

describe('alta de un hallazgo', () => {
  it('manda los campos obligatorios y la severidad que la base acepta', async () => {
    /**
     * `code` y `title` son NOT NULL y no se mandaban; `severity` viajaba como
     * 'alta', que viola el CHECK `IN ('minor','major','critical')`. La fila
     * nunca entraba y el `.catch` vacio se comia el error.
     */
    const { result } = await montar([]);

    act(() => {
      result.current.a.addNonConformity({
        tenantId: 'a0000000-0000-0000-0000-000000000001',
        plantId: 'c0000000-0000-0000-0000-000000000001',
        hallazgo: 'Derrame sin contencion',
        criticidad: 'alta',
        responsableId: 'd0000000-0000-0000-0000-000000000001',
      });
    });

    await waitFor(() => expect(post).toHaveBeenCalled());
    const cuerpo = post.mock.calls[0]![1] as Record<string, unknown>;
    expect(cuerpo.severity).toBe('critical');
    expect(cuerpo.code).toBeTruthy();
    expect(cuerpo.title).toBeTruthy();
  });

  it('reemplaza el id local por el que asigna la API', async () => {
    // El id optimista es `nc-<timestamp>`, que la API no conoce. Sin el
    // reemplazo, toda escritura posterior sobre ese hallazgo apunta a una fila
    // inexistente y vuelve a fallar en silencio.
    const { result } = await montar([]);

    act(() => {
      result.current.a.addNonConformity({
        tenantId: 'a0000000-0000-0000-0000-000000000001',
        plantId: 'c0000000-0000-0000-0000-000000000001',
        hallazgo: 'Derrame sin contencion',
        criticidad: 'media',
        responsableId: 'd0000000-0000-0000-0000-000000000001',
      });
    });

    await waitFor(() => expect(result.current.a.nonConformities[0]?.id).toBe(NC_ID));
  });

  it('saca de la pantalla el hallazgo que la API rechazo', async () => {
    const { result } = await montar([]);
    post.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'code ya existe' }));

    act(() => {
      result.current.a.addNonConformity({
        tenantId: 'a0000000-0000-0000-0000-000000000001',
        plantId: 'c0000000-0000-0000-0000-000000000001',
        hallazgo: 'Derrame sin contencion',
        criticidad: 'baja',
        responsableId: 'd0000000-0000-0000-0000-000000000001',
      });
    });

    await waitFor(() => expect(result.current.toast.toasts).toHaveLength(1));
    expect(result.current.a.nonConformities).toHaveLength(0);
  });
});

/**
 * Un fallo de la API no puede dejar la pantalla colgada.
 *
 * **Lo que este archivo NO puede probar** es que un fallo conserve los datos
 * de ejemplo: stubea `@/mocks/audits` a vacio a proposito —"lo que se mida
 * viene de la API o no viene"— asi que no hay nada que conservar.
 *
 * Por eso las pruebas de "cero filas no muestra los ejemplos" (#208) viven en
 * `stores-sin-datos.test.tsx`, donde los datos de ejemplo reales si estan. Una
 * version anterior las puso aca y **sobrevivian a la mutacion**: afirmaban 0 y
 * obtenian 0 con el arreglo puesto o quitado.
 */
describe('cuando la API falla', () => {
  it('la pantalla termina de cargar igual', async () => {
    iniciarSesionComo('admin_empresa');
    get.mockRejectedValue(new Error('sin red'));

    const r = renderHook(() => ({ a: useAudits(), toast: useToast() }), { wrapper });

    await waitFor(() => expect(r.result.current.a.loading).toBe(false));
  });
});
