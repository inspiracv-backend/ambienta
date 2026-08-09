'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Bell, LogOut, Menu } from 'lucide-react';
import { UserButton } from '@clerk/nextjs';
import { Avatar, Button } from '@/components/atoms';
import { CLERK_HABILITADO } from '@/lib/clerk-config';
import { useSession } from '@/lib/session';
import { useNotifications } from '@/lib/notifications-store';
import { ROLE_LABEL } from '@/lib/roles';
import { navItemsParaRol } from '@/lib/navigation';
import { mockTenants } from '@/mocks/tenants';

interface AppHeaderProps {
  onOpenMobileNav: () => void;
}

/**
 * Header persistente: tenant + rol activo siempre visibles (H1 🔴 crítica).
 * No debe requerir navegar para saber "dónde estoy".
 */
export function AppHeader({ onOpenMobileNav }: AppHeaderProps) {
  const router = useRouter();
  const { user, logout } = useSession();
  const { notifications } = useNotifications();

  const tenant = mockTenants.find((t) => t.id === user?.tenantId);
  const noLeidas = user ? notifications.filter((n) => n.userId === user.id && !n.leida).length : 0;

  // La campana se deriva del propio menú del rol para no duplicar el criterio:
  // /notificaciones es una ruta de tenant, así que al Superadmin lo rebotaría
  // `TenantScopeGate`. Mostrarle el enlace sería ofrecerle una acción que
  // falla al hacer clic. La matriz de permisos le da "recibe alertas de
  // agentes", pero ese centro de notificaciones de plataforma no existe
  // todavía — gap documentado, no un olvido.
  const tieneNotificaciones = user
    ? navItemsParaRol(user.role).some((item) => item.href === '/notificaciones')
    : false;

  function handleLogout() {
    logout();
    router.push('/login');
  }

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 md:px-6">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenMobileNav}
          aria-label="Abrir navegación"
          className="mr-1 text-slate-500 hover:text-slate-800 md:hidden"
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-semibold text-slate-900">{tenant?.nombre ?? 'Ambienta'}</span>
          {user && (
            <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
              {ROLE_LABEL[user.role]}
            </span>
          )}
        </div>
      </div>

      {user && (
        <div className="flex items-center gap-3">
          {tieneNotificaciones && (
            <Link
              href="/notificaciones"
              aria-label={noLeidas > 0 ? `Notificaciones, ${noLeidas} sin leer` : 'Notificaciones'}
              className="relative text-slate-500 hover:text-slate-800"
            >
              <Bell className="h-5 w-5" aria-hidden />
              {noLeidas > 0 && (
                <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-semaforo-no-cumple px-1 text-[10px] font-medium text-white">
                  {noLeidas}
                </span>
              )}
            </Link>
          )}
          <Link href="/perfil" className="flex items-center gap-2 hover:opacity-80" aria-label="Ir a mi perfil">
            <Avatar nombre={user.nombre} avatarUrl={user.avatarUrl} size="sm" />
            <span className="hidden text-sm text-slate-700 sm:inline">{user.nombre}</span>
          </Link>
          {/* Con proveedor real, el menú de cuenta lo maneja él: cerrar sesión
              tiene que invalidar la sesión en Clerk, no solo limpiar el estado
              local. Sin proveedor queda el botón de siempre. */}
          {CLERK_HABILITADO ? (
            <UserButton afterSignOutUrl="/login" />
          ) : (
            <Button variant="ghost" size="md" onClick={handleLogout} aria-label="Cerrar sesión">
              <LogOut className="h-4 w-4" aria-hidden />
            </Button>
          )}
        </div>
      )}
    </header>
  );
}
