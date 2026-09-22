import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { plazoDesdeCampo, useCatalogosDeMejora } from './catalogos-mejora';
import { AuditLogProvider } from './audit-log-store';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

/** Los plazos de la escala de severidad (RF-100, #41): vacío no es cero. */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/no-conformidades/catalogos',
}));

const get = vi.fn();
const patch = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: { get: (...a: unknown[]) => get(...a), post: vi.fn(), patch: (...a: unknown[]) => patch(...a), delete: vi.fn() },
  };
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuditLogProvider>
        <UsersProvider>
          <SessionProvider>{children}</SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  get.mockImplementation((url: string) =>
    Promise.resolve(
      url.includes('/severidades')
        ? [{ id: 's-1', code: 'major', label: 'Mayor', rank: 2, days_to_close: 30, active: true }]
        : [],
    ),
  );
  patch.mockResolvedValue({});
});

describe('plazoDesdeCampo', () => {
  it('vacío es "sin plazo" (null), no cero', () => {
    expect(plazoDesdeCampo('')).toBeNull();
    expect(plazoDesdeCampo('   ')).toBeNull();
  });
  it('un entero positivo es el plazo', () => {
    expect(plazoDesdeCampo('15')).toBe(15);
  });
  it('cero, negativos y decimales se rechazan en vez de mandarse', () => {
    expect(plazoDesdeCampo('0')).toBeUndefined();
    expect(plazoDesdeCampo('-3')).toBeUndefined();
    expect(plazoDesdeCampo('2.5')).toBeUndefined();
  });
});

describe('editar un nivel', () => {
  it('quitar el plazo manda days_to_close: null explícito', async () => {
    iniciarSesionComo('admin_empresa');
    const { result } = renderHook(() => useCatalogosDeMejora(), { wrapper });
    await waitFor(() => expect(result.current.niveles).toHaveLength(1));

    await act(async () => {
      await result.current.editarNivel('s-1', { daysToClose: null });
    });

    const [url, cuerpo] = patch.mock.calls[0];
    expect(url).toBe('/audits/catalogos/severidades/s-1');
    // Omitirlo sería "no tocarlo": el plazo seguiría en 30.
    expect(cuerpo).toEqual({ days_to_close: null });
  });

  it('lee también los niveles desactivados, para poder reactivarlos', async () => {
    iniciarSesionComo('admin_empresa');
    renderHook(() => useCatalogosDeMejora(), { wrapper });
    await waitFor(() => expect(get).toHaveBeenCalledWith(expect.stringContaining('solo_activas=false'), expect.anything()));
  });
});
