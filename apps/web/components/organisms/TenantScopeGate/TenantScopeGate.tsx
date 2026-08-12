'use client';

import { useEffect, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { esRutaDePlataforma, esRutaDeTenant, rutaInicialParaRol } from '@/lib/navigation';

/**
 * Mantiene separados los dos ámbitos de la aplicación cuando se llega por URL
 * directa, no solo por el menú:
 *
 * - El Superadmin (A0, `tenantId: null`) administra la plataforma, no el
 *   contenido de los tenants — CLAUDE.md: "Admin Global NO puede editar
 *   contenido de tenants". Sin este gate, entrar a /matriz-legal le mostraba
 *   una pantalla vacía con un botón "Gestionar RCAs / ISO", ofreciéndole
 *   justamente la acción que tiene prohibida. Su lectura de un tenant (marcada
 *   "L" en la matriz de permisos, para soporte y auditoría) debe hacerse
 *   entrando al tenant desde Gestión de Tenants.
 *
 * - A la inversa, los roles de tenant no acceden a la administración de la
 *   plataforma (/gestion-tenants, /soporte).
 *
 * Organismo cross-cutting, mismo criterio que `ClienteInvitadoGate` y
 * `PerfilEmpresaGate`: la lógica de negocio no vive en `DashboardLayout`.
 *
 * Esto es UX, no seguridad: la barrera real es el RBAC en la API, que no
 * existe todavía (propuesta OpenSpec sistema-actores-roles-rbac).
 */
export function TenantScopeGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user } = useSession();

  const esSuperadmin = user?.role === 'superadmin';
  const fueraDeAmbito = user
    ? (esSuperadmin && esRutaDeTenant(pathname)) || (!esSuperadmin && esRutaDePlataforma(pathname))
    : false;

  useEffect(() => {
    if (fueraDeAmbito && user) router.replace(rutaInicialParaRol(user.role));
  }, [fueraDeAmbito, user, router]);

  if (fueraDeAmbito) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner label="Esta sección no corresponde a tu rol, redirigiendo" />
      </div>
    );
  }

  return <>{children}</>;
}
