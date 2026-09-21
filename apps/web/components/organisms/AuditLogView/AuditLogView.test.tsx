import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { AuditLogView } from './AuditLogView';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { TenantsProvider } from '@/lib/tenants-store';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { ApiError } from '@/lib/api-client';
import { iniciarSesionComo } from '@/test/utils';

/**
 * La pantalla del registro lee el servidor (decisión 10 del 21-sep). Hasta ese
 * día mostraba solo lo de la sesión y se vaciaba al recargar.
 */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/historial',
}));

const getPagina = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: {
      get: vi.fn().mockResolvedValue([]),
      getPagina: (...a: unknown[]) => getPagina(...a),
      post: vi.fn(),
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
            <TenantsProvider>{children}</TenantsProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

const FILA = {
  id: 7,
  occurred_at: '2026-09-21T15:00:00Z',
  actor_user_id: 'u1',
  actor_nombre: 'Marcelo Fuentes',
  action: 'download',
  entity_type: 'audits',
  entity_id: 'a0000030-0000-0000-0000-000000000001',
  reason: null,
  before_data: null,
  after_data: { titulo: 'Informe AUD-2026-001', formato: 'pdf', filas: 5 },
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

function montar() {
  const u = iniciarSesionComo('admin_empresa');
  getPagina.mockImplementation(() =>
    Promise.resolve({ datos: [{ ...FILA, tenant_id: u.tenantId }], hayMas: false }),
  );
  render(<AuditLogView tenantIdVisible={u.tenantId} />, { wrapper });
  return u;
}

describe('el registro de actividades', () => {
  it('muestra lo que guardo el servidor', async () => {
    const u = montar();

    expect(await screen.findByText('Emitió "Informe AUD-2026-001" (PDF, 5 filas)')).toBeTruthy();
    expect(screen.getAllByText(/Marcelo Fuentes/).length).toBeGreaterThan(0);
    expect(getPagina).toHaveBeenCalledWith('/system/audit-log?limit=500', { tenantId: u.tenantId });
  });

  it('si la pagina vino cortada, lo dice', async () => {
    const u = iniciarSesionComo('admin_empresa');
    getPagina.mockResolvedValue({ datos: [{ ...FILA, tenant_id: u.tenantId }], hayMas: true });
    render(<AuditLogView tenantIdVisible={u.tenantId} />, { wrapper });

    expect(await screen.findByText(/Se muestran los 500 eventos más recientes/)).toBeTruthy();
  });

  it('si no pudo leer el servidor, lo dice en vez de mostrar solo la sesion como si fuera todo', async () => {
    const u = iniciarSesionComo('admin_empresa');
    getPagina.mockRejectedValue(new ApiError(403, 'Forbidden', { detail: { mensaje: 'Sin permiso' } }));
    render(<AuditLogView tenantIdVisible={u.tenantId} />, { wrapper });

    expect(await screen.findByText(/No se pudo leer el registro del servidor/)).toBeTruthy();
  });
});
