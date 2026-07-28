'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSession } from '@/lib/session';
import { navItemsParaRol, type NavItem } from '@/lib/navigation';

interface AppSidebarProps {
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}

function isActiveHref(href: string, pathname: string) {
  return href !== '#' && (pathname === href || pathname.startsWith(`${href}/`));
}

/**
 * Los ítems y su visibilidad por rol viven en `lib/navigation.ts`, derivados
 * de la matriz de permisos del Análisis de Actores — este componente solo los
 * dibuja. Antes el menú listaba los 12 módulos del tenant para todos y al
 * Superadmin le agregaba los suyos al final, así que veía pantallas de un
 * tenant al que no pertenece (y que le salían vacías, porque su `tenantId`
 * es null).
 */
function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useSession();

  if (!user) return null;

  return (
    <>
      {navItemsParaRol(user.role).map((item) => (
        <SidebarLink key={item.label} item={item} active={isActiveHref(item.href, pathname)} onNavigate={onNavigate} />
      ))}
    </>
  );
}

/** Sidebar persistente en desktop (H1); en mobile es un drawer accesible (Radix Dialog) — RNF-15 responsive. */
export function AppSidebar({ mobileOpen, onMobileOpenChange }: AppSidebarProps) {
  return (
    <>
      <nav
        aria-label="Navegación principal"
        className="hidden w-60 shrink-0 flex-col gap-1 border-r border-slate-200 bg-white p-3 md:flex"
      >
        <NavLinks />
      </nav>

      <Dialog.Root open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 md:hidden" />
          <Dialog.Content
            aria-label="Navegación principal"
            className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col gap-1 bg-white p-3 shadow-lg md:hidden"
          >
            <div className="mb-2 flex items-center justify-between">
              <Dialog.Title className="text-sm font-semibold text-slate-700">Navegación</Dialog.Title>
              <Dialog.Close aria-label="Cerrar navegación" className="text-slate-400 hover:text-slate-700">
                <X className="h-5 w-5" aria-hidden />
              </Dialog.Close>
            </div>
            <NavLinks onNavigate={() => onMobileOpenChange(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}

function SidebarLink({
  item,
  active,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  onNavigate?: () => void;
}) {
  const ItemIcon = item.icon;
  const content = (
    <span className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm">
      <ItemIcon className="h-4 w-4 shrink-0" aria-hidden />
      {item.label}
      {!item.enabled && (
        <span className="ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
          Próximamente
        </span>
      )}
    </span>
  );

  if (!item.enabled) {
    return (
      <span
        aria-disabled="true"
        title="Disponible en una próxima iteración"
        className={cn('cursor-not-allowed text-slate-400')}
      >
        {content}
      </span>
    );
  }

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn('font-medium text-slate-700 hover:bg-slate-50', active && 'bg-brand-50 text-brand-700')}
    >
      {content}
    </Link>
  );
}
