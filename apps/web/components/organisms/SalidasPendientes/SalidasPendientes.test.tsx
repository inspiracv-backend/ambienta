import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { SessionProvider } from '@/lib/session';
import { UsersProvider } from '@/lib/users-store';
import { ToastProvider } from '@/lib/toast-store';
import { iniciarSesionComo } from '@/test/utils';
import { SalidasPendientes } from './SalidasPendientes';

const get = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return { ...real, api: { get: (...a: unknown[]) => get(...a) } };
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>{children}</SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

function montar() {
  iniciarSesionComo('admin_empresa');
  return render(<SalidasPendientes />, { wrapper });
}

beforeEach(() => vi.clearAllMocks());

describe('las salidas que el sistema de gestion todavia debe', () => {
  it('se listan con su registro, su responsable y su plazo', async () => {
    get.mockResolvedValue([
      {
        id: 'c-1',
        nonconformity_id: 'nc-9',
        kind: 'matriz_riesgos',
        status: 'pendiente',
        responsable_nombre: 'Ana Rojas',
        due_date: '2026-12-01',
        nonconformity_code: 'NC-2026-003',
      },
    ]);
    montar();

    expect(await screen.findByText('Actualizar matriz de riesgos y oportunidades')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'NC-2026-003' }).getAttribute('href')).toBe('/no-conformidades/nc-9');
    expect(screen.getByText(/Ana Rojas/)).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/audits/compromisos?estado=pendiente', { tenantId: expect.any(String) });
  });

  it('ninguna pendiente se dice, y no se confunde con no haber preguntado', async () => {
    get.mockResolvedValue([]);
    montar();

    expect(await screen.findByText(/Ninguna pendiente/)).toBeTruthy();
  });

  it('si no se pudo preguntar lo dice: el vacio seria una afirmacion falsa', async () => {
    get.mockRejectedValue(new Error('sin red'));
    montar();

    expect((await screen.findByRole('alert')).textContent).toMatch(/No se pudieron cargar/);
    expect(screen.queryByText(/Ninguna pendiente/)).toBeNull();
  });
});
