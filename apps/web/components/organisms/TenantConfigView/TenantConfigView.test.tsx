import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { TenantConfigView } from './TenantConfigView';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { TenantsProvider } from '@/lib/tenants-store';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';
import { mockTenants } from '@/mocks/tenants';

/**
 * El aviso de suspender una empresa no puede inventar cuántas personas pierden
 * el acceso. Antes el número salía de `mockUsers` y con empresas reales decía
 * «Los 0 usuarios perderán acceso».
 */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/gestion-tenants/x',
}));

vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return { ...real, api: { get: vi.fn().mockResolvedValue([]), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
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

const ACTIVA = { ...mockTenants[0], estado: 'activo' as const };

beforeEach(() => {
  window.localStorage.clear();
  iniciarSesionComo('superadmin');
});

async function abrirSuspender() {
  await userEvent.click(screen.getByRole('button', { name: /Suspender/ }));
}

describe('cuántas personas pierden acceso', () => {
  it('sin poder contarlas, no inventa un número', async () => {
    render(<TenantConfigView tenant={ACTIVA} userCount={null} />, { wrapper });
    await abrirSuspender();
    expect(screen.getAllByText(/Todos los usuarios/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Los 0 usuarios/)).not.toBeInTheDocument();
  });

  it('cuando se sabe, lo dice', async () => {
    render(<TenantConfigView tenant={ACTIVA} userCount={7} />, { wrapper });
    await abrirSuspender();
    expect(screen.getAllByText(/Los 7 usuarios/).length).toBeGreaterThan(0);
  });
});
