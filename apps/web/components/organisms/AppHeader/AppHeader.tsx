'use client';

import { useRouter } from 'next/navigation';
import { LogOut, Menu } from 'lucide-react';
import { Avatar, Button } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { ROLE_LABEL } from '@/lib/roles';
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

  const tenant = mockTenants.find((t) => t.id === user?.tenantId);

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
          <Avatar nombre={user.nombre} avatarUrl={user.avatarUrl} size="sm" />
          <span className="hidden text-sm text-slate-700 sm:inline">{user.nombre}</span>
          <Button variant="ghost" size="md" onClick={handleLogout} aria-label="Cerrar sesión">
            <LogOut className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      )}
    </header>
  );
}
