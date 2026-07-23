'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import {
  LayoutDashboard,
  ScrollText,
  ClipboardList,
  CalendarDays,
  ShieldAlert,
  BookMarked,
  Building2,
  FileBarChart,
  Bell,
  Users,
  Bot,
  Settings,
  ServerCog,
  LifeBuoy,
  FlaskConical,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSession } from '@/lib/session';

/**
 * Navegación global sugerida (Esquema de Pantallas v1.5). Solo "Dashboard"
 * tiene ruta implementada en esta iteración — el resto se muestra
 * deshabilitado con nota "Próximamente" (H1: no ofrecer una acción que
 * fallaría silenciosamente).
 */
const NAV_ITEMS = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, enabled: true },
  { label: 'Matriz Legal', href: '/matriz-legal', icon: ScrollText, enabled: true },
  { label: 'Obligaciones', href: '/obligaciones', icon: ClipboardList, enabled: true },
  { label: 'Calendario / Gantt', href: '/calendario', icon: CalendarDays, enabled: true },
  { label: 'Auditorías', href: '#', icon: ShieldAlert, enabled: false },
  { label: 'No Conformidades', href: '#', icon: ShieldAlert, enabled: false },
  { label: 'Catálogo Normativo', href: '#', icon: BookMarked, enabled: false },
  { label: 'Gestores', href: '#', icon: Building2, enabled: false, gestorOnly: true },
  { label: 'Reportes', href: '#', icon: FileBarChart, enabled: false },
  { label: 'Notificaciones', href: '#', icon: Bell, enabled: false },
  { label: 'Usuarios y Roles', href: '#', icon: Users, enabled: false },
  { label: 'Chatbot', href: '#', icon: Bot, enabled: false },
  { label: 'Configuración / Perfil', href: '#', icon: Settings, enabled: false },
] as const;

const SUPERADMIN_ITEMS = [
  { label: 'Gestión de Tenants', href: '#', icon: ServerCog, enabled: false },
  { label: 'Soporte', href: '#', icon: LifeBuoy, enabled: false },
  { label: 'Planes de prueba', href: '#', icon: FlaskConical, enabled: false },
] as const;

interface AppSidebarProps {
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}

function useNavItems() {
  const { user } = useSession();
  const isGestorTenant = user?.role === 'gestor';
  const items = NAV_ITEMS.filter((item) => !('gestorOnly' in item && item.gestorOnly) || isGestorTenant);
  return { items, isSuperadmin: user?.role === 'superadmin' };
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { items, isSuperadmin } = useNavItems();

  return (
    <>
      {items.map((item) => (
        <SidebarLink
          key={item.label}
          item={item}
          active={item.href !== '#' && (pathname === item.href || pathname.startsWith(`${item.href}/`))}
          onNavigate={onNavigate}
        />
      ))}

      {isSuperadmin && (
        <>
          <hr className="my-2 border-slate-200" />
          {SUPERADMIN_ITEMS.map((item) => (
            <SidebarLink key={item.label} item={item} active={false} onNavigate={onNavigate} />
          ))}
        </>
      )}
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
  item: { label: string; href: string; icon: typeof LayoutDashboard; enabled: boolean };
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
