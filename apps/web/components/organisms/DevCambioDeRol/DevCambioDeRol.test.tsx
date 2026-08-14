import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { DevCambioDeRol } from './DevCambioDeRol';
import { SessionProvider } from '@/lib/session';
import { UsersProvider } from '@/lib/users-store';
import { ToastProvider } from '@/lib/toast-store';
import { iniciarSesionComo } from '@/test/utils';

const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: (...a: unknown[]) => push(...a), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/dashboard',
}));

/** Se controla por prueba: es lo que decide si el componente existe. */
const clerk = vi.hoisted(() => ({ habilitado: false }));
vi.mock('@/lib/clerk-config', () => ({
  get CLERK_HABILITADO() {
    return clerk.habilitado;
  },
  CLERK_JWT_TEMPLATE: 'default',
}));

function montar() {
  return render(
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>
          <DevCambioDeRol />
        </SessionProvider>
      </UsersProvider>
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  clerk.habilitado = false;
  window.localStorage.clear();
});

describe('DevCambioDeRol', () => {
  it('no se muestra con el proveedor de identidad configurado', async () => {
    /**
     * La propiedad que más importa de este componente.
     *
     * Con Clerk activo la API valida la firma del JWT, así que una sesión
     * fabricada en el navegador entra a la interfaz y después cobra 401 en cada
     * llamada: la pantalla se ve bien y no hay datos. Ofrecerlo sería peor que
     * no tenerlo.
     */
    clerk.habilitado = true;

    // Se monta pelado, sin los providers, a proposito: el guard corta antes de
    // tocar la sesion. Envolverlo en `SessionProvider` con la bandera activa
    // exigiria el contexto de Clerk y estariamos probando el arnes, no esto.
    const { container } = render(<DevCambioDeRol />);

    expect(container).toBeEmptyDOMElement();
  });

  it('no se muestra sin sesión iniciada', async () => {
    montar();
    await waitFor(() => expect(screen.queryByRole('button')).not.toBeInTheDocument());
  });

  it('muestra el rol actual en el botón cerrado', async () => {
    iniciarSesionComo('admin_empresa');
    montar();

    expect(await screen.findByRole('button', { name: /admin/i })).toBeInTheDocument();
  });

  it('al abrirlo lista los usuarios disponibles', async () => {
    iniciarSesionComo('admin_empresa');
    montar();

    await userEvent.click(await screen.findByRole('button', { name: /admin/i }));

    // Más de uno: si listara solo el actual, no serviría para cambiar.
    await waitFor(() => expect(screen.getAllByRole('button').length).toBeGreaterThan(2));
  });

  it('el usuario actual no se puede volver a elegir', async () => {
    const actual = iniciarSesionComo('admin_empresa');
    montar();

    await userEvent.click(await screen.findByRole('button', { name: /admin/i }));

    const suyo = await screen.findByRole('button', { name: new RegExp(actual.nombre, 'i') });
    expect(suyo).toBeDisabled();
    expect(suyo).toHaveAttribute('aria-current', 'true');
  });

  it('al cambiar de rol lleva a la pantalla inicial de ese rol', async () => {
    /**
     * No basta con cambiar la sesión: un Cliente Invitado que aterriza en el
     * tablero de empresa lo ve vacío, y parece un error del sistema en vez de
     * la consecuencia de su alcance.
     */
    iniciarSesionComo('admin_empresa');
    montar();

    await userEvent.click(await screen.findByRole('button', { name: /admin/i }));
    const otro = screen.getAllByRole('button').find((b) => !b.hasAttribute('disabled') && b.textContent?.trim());
    await userEvent.click(otro!);

    await waitFor(() => expect(push).toHaveBeenCalled());
    expect(String(push.mock.calls[0][0])).toMatch(/^\//);
  });
});
