import { describe, expect, it } from 'vitest';
import type { Role } from '@ambienta/shared';
import {
  esRutaDePlataforma,
  esRutaDeTenant,
  navItemsParaRol,
  rutaInicialParaRol,
  PLATFORM_NAV_ITEMS,
  TENANT_NAV_ITEMS,
} from './navigation';

/**
 * Estos tests fijan la matriz de permisos por módulo (§4 del Análisis de
 * Actores) como contrato verificable. Son la red de seguridad de la separación
 * entre el ámbito de plataforma y el de tenant: si alguien agrega un módulo al
 * menú sin declarar sus roles, o le devuelve al Superadmin los módulos de un
 * tenant, esto falla.
 */

function hrefs(role: Role): string[] {
  return navItemsParaRol(role).map((i) => i.href);
}

describe('navItemsParaRol — Superadmin (A0)', () => {
  it('solo ve módulos de plataforma', () => {
    expect(hrefs('superadmin')).toEqual([
      '/plataforma',
      '/gestion-tenants',
      '/soporte',
      '/chatbot',
      '/perfil',
      '#',
    ]);
  });

  it('NO ve ningún módulo de negocio del tenant', () => {
    const suyos = hrefs('superadmin');
    const deTenant = [
      '/dashboard',
      '/matriz-legal',
      '/obligaciones',
      '/calendario',
      '/auditorias',
      '/no-conformidades',
      '/catalogo-normativo',
      '/gestores',
      '/reportes',
      '/notificaciones',
      '/usuarios',
      '/perfil-empresa',
    ];
    for (const ruta of deTenant) {
      expect(suyos, `el Superadmin no debe ver ${ruta}`).not.toContain(ruta);
    }
  });
});

describe('navItemsParaRol — roles de tenant', () => {
  it('el Admin Empresa (A1) gestiona la empresa pero no ve Gestores', () => {
    const suyos = hrefs('admin_empresa');
    expect(suyos).toContain('/perfil-empresa');
    expect(suyos).toContain('/usuarios');
    expect(suyos).not.toContain('/gestores');
  });

  it('el Gestor (A4) es A1 + el módulo Gestores', () => {
    const gestor = hrefs('gestor');
    const admin = hrefs('admin_empresa');
    expect(gestor).toContain('/gestores');
    // Todo lo del Admin Empresa está disponible para el Gestor.
    for (const ruta of admin) {
      expect(gestor, `el Gestor debería ver ${ruta}`).toContain(ruta);
    }
    expect(gestor).toHaveLength(admin.length + 1);
  });

  it('el Usuario Interno (A2) opera pero no administra', () => {
    const suyos = hrefs('usuario_interno');
    // La matriz le da "L propio perfil" (que es /perfil), no la gestión de la
    // empresa; gestionar usuarios y el módulo Gestores le marcan "—".
    expect(suyos).not.toContain('/perfil-empresa');
    expect(suyos).not.toContain('/usuarios');
    expect(suyos).not.toContain('/gestores');
    // Pero sí opera el día a día.
    expect(suyos).toContain('/obligaciones');
    expect(suyos).toContain('/calendario');
    expect(suyos).toContain('/no-conformidades');
    expect(suyos).toContain('/perfil');
  });

  it('ningún rol de tenant accede a la administración de la plataforma', () => {
    for (const role of ['admin_empresa', 'usuario_interno', 'gestor'] as const) {
      expect(hrefs(role)).not.toContain('/gestion-tenants');
      expect(hrefs(role)).not.toContain('/soporte');
    }
  });
});

describe('rutaInicialParaRol', () => {
  it('manda al Superadmin a su dashboard de plataforma, no al de un tenant', () => {
    // /dashboard filtra por tenantId y el Superadmin tiene tenantId null:
    // siempre le saldría vacío.
    expect(rutaInicialParaRol('superadmin')).toBe('/plataforma');
    expect(esRutaDeTenant(rutaInicialParaRol('superadmin'))).toBe(false);
  });

  it('manda al Cliente Invitado a sus tickets (RF-05)', () => {
    expect(rutaInicialParaRol('cliente_invitado')).toBe('/crear-ticket');
  });

  it('manda a los roles de tenant al dashboard', () => {
    expect(rutaInicialParaRol('admin_empresa')).toBe('/dashboard');
    expect(rutaInicialParaRol('usuario_interno')).toBe('/dashboard');
    expect(rutaInicialParaRol('gestor')).toBe('/dashboard');
  });

  it('la ruta inicial de cada rol es una que ese rol puede ver', () => {
    for (const role of ['superadmin', 'admin_empresa', 'usuario_interno', 'gestor'] as const) {
      expect(hrefs(role), `${role} no puede ver su propia ruta inicial`).toContain(rutaInicialParaRol(role));
    }
  });
});

describe('clasificación de rutas', () => {
  it('reconoce rutas de tenant, incluidas las anidadas', () => {
    expect(esRutaDeTenant('/matriz-legal')).toBe(true);
    expect(esRutaDeTenant('/matriz-legal/norma-1')).toBe(true);
    expect(esRutaDeTenant('/no-conformidades/nueva')).toBe(true);
    expect(esRutaDeTenant('/gestion-tenants')).toBe(false);
  });

  it('reconoce rutas de plataforma', () => {
    expect(esRutaDePlataforma('/gestion-tenants')).toBe(true);
    expect(esRutaDePlataforma('/gestion-tenants/tenant-1')).toBe(true);
    expect(esRutaDePlataforma('/soporte')).toBe(true);
    expect(esRutaDePlataforma('/dashboard')).toBe(false);
  });

  it('no confunde rutas que comparten prefijo de texto', () => {
    // /perfil y /perfil-empresa son distintas: la primera es de todos los
    // roles, la segunda solo de Admin Empresa y Gestor.
    expect(esRutaDeTenant('/perfil')).toBe(false);
    expect(esRutaDeTenant('/perfil-empresa')).toBe(true);
  });

  it('ninguna ruta es de tenant y de plataforma a la vez', () => {
    const todas = [...TENANT_NAV_ITEMS, ...PLATFORM_NAV_ITEMS].map((i) => i.href).filter((h) => h !== '#');
    for (const href of todas) {
      expect(
        esRutaDeTenant(href) && esRutaDePlataforma(href),
        `${href} está clasificada en ambos ámbitos`,
      ).toBe(false);
    }
  });
});

describe('consistencia del menú', () => {
  it('cada ítem habilitado declara al menos un rol', () => {
    for (const item of [...TENANT_NAV_ITEMS, ...PLATFORM_NAV_ITEMS]) {
      expect(item.roles.length, `${item.label} no declara roles`).toBeGreaterThan(0);
    }
  });

  it('no hay rutas duplicadas dentro del menú de un mismo rol', () => {
    for (const role of ['superadmin', 'admin_empresa', 'usuario_interno', 'gestor'] as const) {
      const rutas = hrefs(role).filter((h) => h !== '#');
      expect(new Set(rutas).size, `${role} tiene rutas duplicadas`).toBe(rutas.length);
    }
  });

  it('el Cliente Invitado no tiene menú de negocio', () => {
    // Está confinado a sus tickets por ClienteInvitadoGate (RF-05).
    expect(navItemsParaRol('cliente_invitado')).toHaveLength(0);
  });

  it('Perfil Empresa y Usuarios y Roles se ofrecen exactamente a los mismos roles', () => {
    // Ambas son "administrar la empresa": si divergen, un rol vería una y no
    // la otra sin razón. Este test nació de un bug real — el menú ofrecía
    // Usuarios y Roles al Gestor mientras la página lo rebotaba, porque el
    // criterio estaba duplicado en dos lugares.
    const rolesDe = (href: string) =>
      (['admin_empresa', 'usuario_interno', 'gestor'] as const).filter((r) =>
        navItemsParaRol(r).some((i) => i.href === href),
      );
    expect(rolesDe('/usuarios')).toEqual(rolesDe('/perfil-empresa'));
  });
});
