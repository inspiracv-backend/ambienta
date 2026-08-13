import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { DepartamentosProvider, useDepartamentos } from './departamentos-store';
import { AuditLogProvider } from './audit-log-store';
import { ToastProvider, useToast } from './toast-store';
import { SessionProvider } from './session';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';
import { ApiError } from './api-client';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/mapa-procesos',
}));

vi.mock('@/mocks/departamentos', () => ({ mockDepartamentos: [] }));

const get = vi.fn();
const post = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...args: unknown[]) => get(...args),
      post: (...args: unknown[]) => post(...args),
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
            <DepartamentosProvider>{children}</DepartamentosProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

function montar() {
  iniciarSesionComo('admin_empresa');
  return renderHook(() => ({ depts: useDepartamentos(), toast: useToast() }), { wrapper });
}

const alta = {
  tenantId: 't-1',
  nombre: 'Chancado y Molienda',
  tipo: 'operativo' as const,
};

beforeEach(() => {
  vi.clearAllMocks();
  get.mockResolvedValue([]);
  window.localStorage.clear();
});

describe('addDepartamento', () => {
  it('adopta el id que devuelve la API en vez del provisional', async () => {
    post.mockResolvedValue({
      id: 'a0000050-0000-0000-0000-000000000009',
      tenant_id: 't-1',
      name: 'Chancado y Molienda',
      process_type: 'operational',
    });

    const { result } = montar();
    await waitFor(() => expect(result.current.depts.loading).toBe(false));

    act(() => result.current.depts.addDepartamento(alta));

    // Esta es la propiedad que importa: si la fila se queda con el id
    // provisional, cualquier edicion posterior apunta a algo que no existe.
    await waitFor(() =>
      expect(result.current.depts.departamentos[0].id).toBe(
        'a0000050-0000-0000-0000-000000000009',
      ),
    );
    expect(result.current.depts.departamentos[0].id).not.toMatch(/^depto-/);
  });

  it('manda el proceso con codigo derivado y el tipo traducido', async () => {
    post.mockResolvedValue({ id: 'x', name: 'Chancado y Molienda', process_type: 'operational' });

    const { result } = montar();
    await waitFor(() => expect(result.current.depts.loading).toBe(false));
    act(() => result.current.depts.addDepartamento(alta));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [ruta, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];

    expect(ruta).toBe('/processes/');
    // 'operativo' es nuestro; la base solo acepta el CHECK en ingles.
    expect(cuerpo.process_type).toBe('operational');
    // 'Chancado y Molienda' → CHANCADOYMOLIENDA → los primeros 10.
    expect(cuerpo.code).toBe('PROC-CHANCADOYM');
    expect(cuerpo.name).toBe('Chancado y Molienda');
  });

  it('retira la fila y avisa cuando la API la rechaza', async () => {
    post.mockRejectedValue(
      new ApiError(409, 'Conflict', { detail: 'Ya existe un proceso con ese codigo.' }),
    );

    const { result } = montar();
    await waitFor(() => expect(result.current.depts.loading).toBe(false));

    act(() => result.current.depts.addDepartamento(alta));
    // Aparece de inmediato: la escritura es optimista.
    expect(result.current.depts.departamentos).toHaveLength(1);

    // Y desaparece al fallar. Dejarla puesta afirmaria que el proceso existe.
    await waitFor(() => expect(result.current.depts.departamentos).toHaveLength(0));

    const toasts = result.current.toast.toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].tipo).toBe('error');
    expect(toasts[0].descripcion).toBe('Ya existe un proceso con ese codigo.');
  });

  it('no llama a la API sin empresa en la sesion', async () => {
    window.localStorage.clear();
    const { result } = renderHook(() => useDepartamentos(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => result.current.addDepartamento(alta));

    // Modo sin backend: la pantalla sigue usable sobre datos de ejemplo.
    expect(post).not.toHaveBeenCalled();
    expect(result.current.departamentos).toHaveLength(1);
  });
});
