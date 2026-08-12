import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { UsersProvider } from '@/lib/users-store';
import { SessionProvider } from '@/lib/session';
import { rutaInicialParaRol } from '@/lib/navigation';
import { Contenido, iniciarSesionComo } from '@/test/utils';
import { TenantScopeGate } from './TenantScopeGate';

/**
 * Este gate es la única barrera del frontend que impide que el Superadmin
 * caiga en los módulos de un tenant escribiendo la URL a mano — y a la
 * inversa. La regla de negocio que protege es explícita en CLAUDE.md:
 * "Admin Global NO puede editar contenido de tenants".
 */

const replace = vi.fn();
let pathname = '/dashboard';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => pathname,
}));

function montar(ruta: string) {
  pathname = ruta;
  return render(
    <UsersProvider>
      <SessionProvider>
        <TenantScopeGate>
          <Contenido />
        </TenantScopeGate>
      </SessionProvider>
    </UsersProvider>,
  );
}

beforeEach(() => {
  replace.mockClear();
});

describe('TenantScopeGate — Superadmin en rutas de tenant', () => {
  it('lo saca de la Matriz Legal y lo manda a su pantalla de inicio', async () => {
    iniciarSesionComo('superadmin');
    montar('/matriz-legal');

    // Se afirma contra `rutaInicialParaRol` y no contra una ruta literal: lo
    // que importa es que aterrice donde le corresponde, no cuál sea hoy.
    await waitFor(() => expect(replace).toHaveBeenCalledWith(rutaInicialParaRol('superadmin')));
    // Y mientras redirige no debe alcanzar a pintar el contenido del tenant.
    expect(screen.queryByTestId('contenido')).not.toBeInTheDocument();
  });

  it('muestra por qué está redirigiendo, en vez de una pantalla muda', async () => {
    iniciarSesionComo('superadmin');
    montar('/obligaciones');

    expect(await screen.findByText(/no corresponde a tu rol/i)).toBeInTheDocument();
  });

  it('también lo saca de una ruta anidada', async () => {
    iniciarSesionComo('superadmin');
    montar('/matriz-legal/norma-123');

    await waitFor(() => expect(replace).toHaveBeenCalledWith(rutaInicialParaRol('superadmin')));
  });

  it('lo deja pasar en sus propias rutas de plataforma', async () => {
    iniciarSesionComo('superadmin');
    montar('/gestion-tenants');

    expect(await screen.findByTestId('contenido')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});

describe('TenantScopeGate — roles de tenant en rutas de plataforma', () => {
  it('saca al Admin Empresa de Gestión de Tenants', async () => {
    iniciarSesionComo('admin_empresa');
    montar('/gestion-tenants');

    await waitFor(() => expect(replace).toHaveBeenCalledWith(rutaInicialParaRol('admin_empresa')));
    expect(screen.queryByTestId('contenido')).not.toBeInTheDocument();
  });

  it('saca al Gestor del módulo de Soporte de plataforma', async () => {
    iniciarSesionComo('gestor');
    montar('/soporte');

    await waitFor(() => expect(replace).toHaveBeenCalledWith(rutaInicialParaRol('admin_empresa')));
  });

  it('deja pasar al Admin Empresa en sus módulos', async () => {
    iniciarSesionComo('admin_empresa');
    montar('/matriz-legal');

    expect(await screen.findByTestId('contenido')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('deja pasar al Usuario Interno en sus obligaciones', async () => {
    iniciarSesionComo('usuario_interno');
    montar('/obligaciones');

    expect(await screen.findByTestId('contenido')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});

describe('TenantScopeGate — casos borde', () => {
  it('sin sesión no redirige ni bloquea: de eso se encargan las páginas', async () => {
    montar('/dashboard');

    expect(await screen.findByTestId('contenido')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('deja pasar a todos en /perfil, que es de ambos ámbitos', async () => {
    iniciarSesionComo('superadmin');
    montar('/perfil');

    expect(await screen.findByTestId('contenido')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
