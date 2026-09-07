/**
 * El historial de presentaciones en el navegador.
 *
 * ## Lo que estas pruebas vigilan
 *
 * No es que el hook pida la ruta — eso se ve leyendo el archivo. Es que **un
 * historial vacío nunca afirme que la declaración no se presentó**, porque hay
 * tres formas de llegar a una lista vacía y sólo una significa eso:
 *
 * | por qué está vacía | lo que significa |
 * |---|---|
 * | la consulta no volvió | no se sabe |
 * | la consulta falló | no se pudo preguntar |
 * | se presentó antes de que existiera el registro | se presentó, sin filas |
 * | de verdad no se ha presentado | no se presentó |
 *
 * En un sistema de cumplimiento, decir "esta declaración nunca se presentó"
 * sobre una que sí se presentó es la afirmación más grave que la pantalla puede
 * hacer: es exactamente lo que un fiscalizador viene a discutir.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { usarPresentaciones } from './usar-presentaciones';
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

const DOS_INTENTOS = [
  {
    id: 'p-2',
    version_no: 2,
    status: 'accepted',
    external_folio: 'SIDREP-2026-99812',
    period_label: '2026-01-01 a 2026-06-30',
    submitted_at: '2026-09-05T12:00:00Z',
    submitted_by: 'u-1',
    reviewed_by: 'u-2',
    submission_data: {},
  },
  {
    id: 'p-1',
    version_no: 1,
    status: 'rejected',
    external_folio: null,
    period_label: '2026-01-01 a 2026-06-30',
    submitted_at: '2026-09-01T12:00:00Z',
    submitted_by: 'u-1',
    reviewed_by: 'u-2',
    submission_data: { motivo_rechazo: 'Falta el anexo de emisiones' },
  },
];

function responder(respuesta: unknown) {
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('/presentaciones')) {
      return respuesta instanceof Error
        ? Promise.reject(respuesta)
        : Promise.resolve(respuesta);
    }
    if (ruta.startsWith('/users/')) return Promise.resolve(mockUsers);
    if (ruta.startsWith('/tenants/')) return Promise.reject(new Error('401'));
    return Promise.resolve([]);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  iniciarSesionComo('admin_empresa');
});

describe('trae cada intento con lo suyo', () => {
  it('conserva el folio de cada version y el motivo de la rechazada', async () => {
    responder(DOS_INTENTOS);
    const { result } = renderHook(() => usarPresentaciones('o-1', 'accepted|X'), {
      wrapper: envoltura,
    });

    await waitFor(() => expect(result.current.presentaciones).not.toBeNull());
    const [ultima, primera] = result.current.presentaciones!;

    expect(ultima.versionNo).toBe(2);
    expect(ultima.folio).toBe('SIDREP-2026-99812');
    // **La v1 conserva SU motivo.** En la obligación se sobrescribe con el del
    // próximo rechazo; acá cada intento guarda el suyo, que es lo que deja ver
    // por qué hicieron falta dos vueltas.
    expect(primera.motivoRechazo).toContain('anexo');
    expect(primera.folio).toBeNull();
  });
});

describe('una lista vacía nunca puede leerse como "no se presentó"', () => {
  it('mientras no vuelve la consulta, no hay lista', async () => {
    // Una promesa que no resuelve: el estado real mientras se espera.
    get.mockImplementation(() => new Promise(() => {}));
    const { result } = renderHook(() => usarPresentaciones('o-1', 'accepted|X'), {
      wrapper: envoltura,
    });

    await new Promise((r) => setTimeout(r, 30));

    expect(result.current.presentaciones).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('si falla, lo dice en vez de devolver una lista vacía a secas', async () => {
    responder(new Error('se cayó la consulta'));
    const { result } = renderHook(() => usarPresentaciones('o-1', 'accepted|X'), {
      wrapper: envoltura,
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());
    // Se afirma que **hay** mensaje, no cuál: `mensajeDeError` normaliza el
    // texto para el usuario, y fijar su redacción acá haría fallar la prueba
    // cada vez que alguien mejore el mensaje sin cambiar el comportamiento.
    expect(result.current.error).toBeTruthy();
    // Y la lista queda vacía, pero acompañada del error: vacía **a secas** es
    // lo que afirmaría que nunca se presentó.
    expect(result.current.presentaciones).toEqual([]);
  });

  it('una declaración sin presentar devuelve la lista vacía, sin error', async () => {
    responder([]);
    const { result } = renderHook(() => usarPresentaciones('o-1', 'draft|'), {
      wrapper: envoltura,
    });

    await waitFor(() => expect(result.current.presentaciones).not.toBeNull());
    expect(result.current.presentaciones).toEqual([]);
    expect(result.current.error).toBeNull();
  });
});

describe('se vuelve a pedir cuando la declaración se mueve', () => {
  it('cambiar el estado dispara una consulta nueva', async () => {
    responder([]);
    const { result, rerender } = renderHook(
      ({ clave }: { clave: string }) => usarPresentaciones('o-1', clave),
      { wrapper: envoltura, initialProps: { clave: 'submitted|' } },
    );

    await waitFor(() => expect(result.current.presentaciones).not.toBeNull());
    const antes = get.mock.calls.filter((c) =>
      String(c[0]).includes('/presentaciones'),
    ).length;

    // Aceptar cambia el estado y el folio: sin revalidar, la ficha mostraría
    // el historial de antes de la acción que el usuario acaba de hacer.
    responder(DOS_INTENTOS);
    rerender({ clave: 'accepted|SIDREP-2026-99812' });

    await waitFor(() =>
      expect(
        get.mock.calls.filter((c) => String(c[0]).includes('/presentaciones')).length,
      ).toBeGreaterThan(antes),
    );
  });
});
