import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { UsersProvider } from '@/lib/users-store';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { iniciarSesionComo } from '@/test/utils';
import { AppSidebar } from './AppSidebar';

/**
 * El menú es lo primero que comunica "qué puedo hacer aquí". Estos tests
 * verifican lo que el usuario realmente ve renderizado, no solo la función
 * que calcula los ítems (eso ya lo cubre lib/navigation.test.ts).
 */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/dashboard',
}));

function montar() {
  render(
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>
          <AppSidebar mobileOpen={false} onMobileOpenChange={vi.fn()} />
        </SessionProvider>
      </UsersProvider>
    </ToastProvider>,
  );
  // El sidebar de escritorio; el drawer móvil es un portal aparte.
  return within(screen.getByRole('navigation', { name: /navegación principal/i }));
}

describe('AppSidebar — Superadmin', () => {
  it('muestra solo la administración de la plataforma', () => {
    iniciarSesionComo('superadmin');
    const nav = montar();

    expect(nav.getByText('Gestión de Tenants')).toBeInTheDocument();
    expect(nav.getByText('Soporte')).toBeInTheDocument();
  });

  it('no ofrece módulos de negocio de un tenant', () => {
    iniciarSesionComo('superadmin');
    const nav = montar();

    for (const modulo of ['Matriz Legal', 'Obligaciones', 'Auditorías', 'Reportes', 'Perfil Empresa']) {
      expect(nav.queryByText(modulo), `el Superadmin no debe ver ${modulo}`).not.toBeInTheDocument();
    }
  });

  it('marca los módulos no construidos como Próximamente en vez de enlazarlos', () => {
    iniciarSesionComo('superadmin');
    const nav = montar();

    // H1: no ofrecer una acción que fallaría en silencio.
    expect(nav.getByText('Próximamente')).toBeInTheDocument();
    expect(nav.getByText('Planes de prueba').closest('a')).toBeNull();
  });
});

describe('AppSidebar — Admin Empresa', () => {
  it('muestra la gestión de la empresa', () => {
    iniciarSesionComo('admin_empresa');
    const nav = montar();

    expect(nav.getByText('Perfil Empresa')).toBeInTheDocument();
    expect(nav.getByText('Usuarios y Roles')).toBeInTheDocument();
    expect(nav.getByText('Matriz Legal')).toBeInTheDocument();
  });

  it('no muestra el módulo de Gestores ni la administración de la plataforma', () => {
    iniciarSesionComo('admin_empresa');
    const nav = montar();

    expect(nav.queryByText('Gestores')).not.toBeInTheDocument();
    expect(nav.queryByText('Gestión de Tenants')).not.toBeInTheDocument();
  });
});

describe('AppSidebar — Gestor', () => {
  it('agrega el módulo de Gestores sobre lo del Admin Empresa', () => {
    iniciarSesionComo('gestor');
    const nav = montar();

    expect(nav.getByText('Gestores')).toBeInTheDocument();
    expect(nav.getByText('Perfil Empresa')).toBeInTheDocument();
    expect(nav.getByText('Usuarios y Roles')).toBeInTheDocument();
  });
});

describe('AppSidebar — Usuario Interno', () => {
  it('muestra lo operativo', () => {
    iniciarSesionComo('usuario_interno');
    const nav = montar();

    expect(nav.getByText('Obligaciones')).toBeInTheDocument();
    expect(nav.getByText('Calendario / Gantt')).toBeInTheDocument();
    expect(nav.getByText('No Conformidades')).toBeInTheDocument();
  });

  it('no muestra lo que es de administración de la empresa', () => {
    iniciarSesionComo('usuario_interno');
    const nav = montar();

    expect(nav.queryByText('Perfil Empresa')).not.toBeInTheDocument();
    expect(nav.queryByText('Usuarios y Roles')).not.toBeInTheDocument();
    expect(nav.queryByText('Gestores')).not.toBeInTheDocument();
  });
});

describe('AppSidebar — sin sesión', () => {
  it('no renderiza enlaces', () => {
    const nav = montar();
    expect(nav.queryAllByRole('link')).toHaveLength(0);
  });
});
