/**
 * Una sesion sin empresa no puede hacer que la aplicacion machaque la API.
 *
 * ## Lo que se midio en el sistema corriendo
 *
 * Con una cuenta de Clerk valida **sin `tenant_id`** en su `publicMetadata`, la
 * API responde `403 sesion_sin_empresa` a toda peticion de negocio. Medido en el
 * log de la API, en 30 minutos y con **una sola carga de pagina**:
 *
 * | Ruta | 403 |
 * |---|---|
 * | `GET /api/v1/tenants/` | 862 |
 * | `GET /api/v1/facilities/` | 862 |
 * | `GET /api/v1/users/` | 4 |
 *
 * En rafagas de **~120 peticiones por segundo**. Las dos primeras van siempre en
 * par porque salen del mismo `Promise.all` de este store; el resto de los
 * providers no aparece porque se cortan solos cuando no hay sesion.
 *
 * El sintoma para quien lo usa no es un error: es que **la pantalla se queda
 * cargando**, porque la pestaña esta ocupada disparando peticiones.
 *
 * ## Que fija esta prueba
 *
 * Que un fallo de carga —cualquiera— se pida **una vez** y se quede quieto. No
 * mira el mensaje ni el estado: cuenta llamadas. Es lo unico que distingue
 * "fallo y lo dice" de "fallo y sigue intentando para siempre".
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { TenantsProvider } from './tenants-store';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { AuditLogProvider } from './audit-log-store';
import { ApiError } from './api-client';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/dashboard',
}));

const get = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      getPagina: vi.fn().mockResolvedValue({ datos: [], hayMas: false }),
      post: vi.fn(),
      patch: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
    },
  };
});

/** El 403 exacto de la API: `detail` es un **objeto** con su codigo. */
function sinEmpresa() {
  return new ApiError(403, 'Forbidden', {
    detail: {
      codigo: 'sesion_sin_empresa',
      mensaje: 'Tu sesion no tiene una empresa asignada.',
    },
  });
}

function envoltura({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>
          <AuditLogProvider>
            <TenantsProvider>{children}</TenantsProvider>
          </AuditLogProvider>
        </SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

beforeEach(() => {
  window.localStorage.clear();
  get.mockReset();
});

/** Cuantas veces se pidio una ruta, sin importar las opciones. */
function llamadasA(ruta: string): number {
  return get.mock.calls.filter((c) => String(c[0]).startsWith(ruta)).length;
}

describe('cuando la API responde 403 a todo', () => {
  it('NO se reintenta en bucle', async () => {
    // La afirmacion central. Con el defecto, este numero crecia sin techo.
    get.mockRejectedValue(sinEmpresa());

    render(<div data-testid="listo" />, { wrapper: envoltura });
    await screen.findByTestId('listo');

    // Se le da tiempo de sobra para que un bucle se note: a 120 req/s, medio
    // segundo son sesenta peticiones.
    await new Promise((r) => setTimeout(r, 500));

    expect(llamadasA('/tenants/')).toBeLessThanOrEqual(2);
    expect(llamadasA('/facilities/')).toBeLessThanOrEqual(2);
  });

  it('y tampoco cuando responde bien', async () => {
    // La otra mitad: que no reintente no puede lograrse dejando de pedir.
    get.mockResolvedValue([]);

    render(<div data-testid="listo" />, { wrapper: envoltura });
    await screen.findByTestId('listo');
    await new Promise((r) => setTimeout(r, 300));

    expect(llamadasA('/tenants/')).toBeGreaterThanOrEqual(1);
    expect(llamadasA('/tenants/')).toBeLessThanOrEqual(2);
  });

  it('la aplicacion sigue pintando: un 403 no deja la pantalla en blanco', async () => {
    get.mockRejectedValue(sinEmpresa());

    render(<div data-testid="contenido">algo</div>, { wrapper: envoltura });

    await waitFor(() => expect(screen.getByTestId('contenido')).toBeInTheDocument());
  });
});
