import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { TareasDelPlanPanel } from './TareasDelPlanPanel';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';
import { ApiError } from '@/lib/api-client';

/** Las tareas del plan de acción (#169): lo que se manda, lo que se lee, y el estado tras un rechazo. */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/planes-accion/p-1',
}));

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), patch: (...a: unknown[]) => patch(...a), delete: vi.fn() },
  };
});

function tarea(over: Record<string, unknown> = {}) {
  return { id: 't-1', title: 'Instalar bandeja', status: 'todo', assignee_user_id: null, due_at: null, completed_at: null, ...over };
}

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

let filas: Record<string, unknown>[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  filas = [tarea()];
  get.mockImplementation((url: string) => Promise.resolve(url.endsWith('/tasks') ? filas : []));
});

async function montar() {
  iniciarSesionComo('admin_empresa');
  render(<TareasDelPlanPanel planId="p-1" />, { wrapper });
}

describe('marcar', () => {
  it('manda done a la tarea del plan', async () => {
    patch.mockResolvedValue(tarea({ status: 'done', completed_at: '2026-09-14T12:00:00Z' }));
    await montar();
    await userEvent.click(await screen.findByRole('button', { name: /Marcar «Instalar bandeja» como hecha/ }));

    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][0]).toBe('/audits/action-plans/tasks/t-1');
    expect(patch.mock.calls[0][1]).toEqual({ status: 'done' });
    expect(await screen.findByRole('button', { name: /Reabrir «Instalar bandeja»/ })).toBeInTheDocument();
  });

  it('si la base lo rechaza, vuelve a como estaba y lo dice', async () => {
    patch.mockRejectedValue(new ApiError(403, 'Forbidden', { detail: 'sin permiso' }));
    await montar();
    await userEvent.click(await screen.findByRole('button', { name: /Marcar «Instalar bandeja» como hecha/ }));

    expect(await screen.findByText(/No se guardó «Instalar bandeja»/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Marcar «Instalar bandeja» como hecha/ })).toHaveAttribute('aria-pressed', 'false');
  });

  it('un estado que no es pendiente ni hecha se muestra y no se pisa con una casilla', async () => {
    filas = [tarea({ status: 'blocked' }), tarea({ id: 't-2', title: 'Otra', status: 'estado_nuevo' })];
    await montar();
    expect(await screen.findByText('Bloqueada')).toBeInTheDocument();
    // Lo que no se reconoce se muestra crudo, no escondido.
    expect(screen.getByText('estado_nuevo')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Marcar/ })).not.toBeInTheDocument();
  });
});

describe('cargar', () => {
  it('si no se pudo preguntar, no dice "no tiene tareas"', async () => {
    get.mockImplementation((url: string) =>
      url.endsWith('/tasks') ? Promise.reject(new ApiError(500, 'Error', null)) : Promise.resolve([]),
    );
    await montar();
    expect(await screen.findByText(/No se pudieron cargar las tareas/)).toBeInTheDocument();
    expect(screen.queryByText(/todavía no tiene tareas/)).not.toBeInTheDocument();
  });
});

describe('agregar', () => {
  it('manda título y fecha al plan, y la muestra con lo que devolvió la base', async () => {
    filas = [];
    post.mockResolvedValue(tarea({ id: 't-9', title: 'Capacitar al turno', due_at: '2026-09-30T23:59:00+00:00' }));
    await montar();
    await screen.findByText(/todavía no tiene tareas/);

    await userEvent.type(screen.getByLabelText('Nueva tarea'), 'Capacitar al turno');
    await userEvent.type(screen.getByLabelText('Vence'), '2026-09-30');
    await userEvent.click(screen.getByRole('button', { name: 'Agregar' }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0][0]).toBe('/audits/action-plans/p-1/tasks');
    expect(post.mock.calls[0][1]).toMatchObject({ title: 'Capacitar al turno', due_at: '2026-09-30T23:59:00' });
    expect(await screen.findByText('Capacitar al turno')).toBeInTheDocument();
  });

  it('si la base la rechaza, no aparece y lo dice', async () => {
    filas = [];
    post.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'x', codigo: 'referencia_inexistente', campos: ['assignee_user_id'] }));
    await montar();
    await screen.findByText(/todavía no tiene tareas/);
    await userEvent.type(screen.getByLabelText('Nueva tarea'), 'Algo');
    await userEvent.click(screen.getByRole('button', { name: 'Agregar' }));

    expect(await screen.findByText(/No se agregó/)).toBeInTheDocument();
    expect(screen.getByText(/todavía no tiene tareas/)).toBeInTheDocument();
  });
});
