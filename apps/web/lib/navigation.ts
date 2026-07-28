import type { Role } from '@ambienta/shared';
import {
  LayoutDashboard,
  ScrollText,
  ClipboardList,
  CalendarDays,
  ShieldAlert,
  BookMarked,
  Building,
  Building2,
  FileBarChart,
  Bell,
  Users,
  Bot,
  Settings,
  ServerCog,
  LifeBuoy,
  FlaskConical,
} from 'lucide-react';

/**
 * Navegación por rol — fuente única de verdad.
 *
 * Los `roles` de cada ítem salen de la matriz de permisos por módulo
 * (§4 de `openspec/changes/sistema-actores-roles-rbac/fuentes/
 * Ambienta_Analisis_Actores_v1.md`), no de criterio propio.
 *
 * Dos ámbitos que NO se mezclan:
 *
 * - **Plataforma (A0 Superadmin):** administra el software, no los datos de
 *   los tenants. CLAUDE.md es explícito: "Admin Global NO puede editar
 *   contenido de tenants". Su acceso de lectura a un tenant (marcado "L" en
 *   la matriz, para soporte y auditoría) ocurre entrando a ese tenant desde
 *   Gestión de Tenants — no teniendo sus módulos en el menú global, donde
 *   además saldrían vacíos porque el Superadmin tiene `tenantId: null`.
 *
 * - **Tenant (A1 Admin Empresa, A2 Usuario Interno, A4 Gestor):** operan
 *   dentro de su empresa y nunca ven la administración de la plataforma.
 *
 * El Cliente Invitado (A3) no aparece: `ClienteInvitadoGate` lo mantiene
 * fuera de todo el área de negocio (RF-05), solo accede a sus tickets.
 *
 * IMPORTANTE: esto es UX, no seguridad. Ocultar un ítem del menú no impide
 * nada por sí solo; la barrera real es el RBAC en la API, que todavía no
 * existe (propuesta OpenSpec sistema-actores-roles-rbac, pendiente de
 * aprobación). `TenantScopeGate` cubre mientras tanto el acceso por URL.
 */

export interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  roles: readonly Role[];
  enabled: boolean;
}

/** Roles que operan dentro de un tenant. */
const TENANT_ROLES = ['admin_empresa', 'usuario_interno', 'gestor'] as const;

/** Solo quien administra la empresa: Admin Empresa y Gestor (A4 = A1 + módulo Gestores). */
const ADMIN_ROLES = ['admin_empresa', 'gestor'] as const;

/**
 * Menú del ámbito tenant. El Usuario Interno (A2) queda fuera de:
 * - Perfil Empresa → la matriz le da "L propio perfil", que es /perfil, no la
 *   gestión de plantas y departamentos de la empresa (esa es "C" solo de A1).
 * - Usuarios y Roles → gestionar usuarios es competencia de A1 (Sección N).
 * - Gestores → la matriz le marca "—" (sin acceso).
 */
export const TENANT_NAV_ITEMS: readonly NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, roles: TENANT_ROLES, enabled: true },
  { label: 'Perfil Empresa', href: '/perfil-empresa', icon: Building, roles: ADMIN_ROLES, enabled: true },
  { label: 'Matriz Legal', href: '/matriz-legal', icon: ScrollText, roles: TENANT_ROLES, enabled: true },
  { label: 'Obligaciones', href: '/obligaciones', icon: ClipboardList, roles: TENANT_ROLES, enabled: true },
  { label: 'Calendario / Gantt', href: '/calendario', icon: CalendarDays, roles: TENANT_ROLES, enabled: true },
  { label: 'Auditorías', href: '/auditorias', icon: ShieldAlert, roles: TENANT_ROLES, enabled: true },
  { label: 'No Conformidades', href: '/no-conformidades', icon: ShieldAlert, roles: TENANT_ROLES, enabled: true },
  { label: 'Catálogo Normativo', href: '/catalogo-normativo', icon: BookMarked, roles: TENANT_ROLES, enabled: true },
  { label: 'Gestores', href: '/gestores', icon: Building2, roles: ['gestor'], enabled: true },
  { label: 'Reportes', href: '/reportes', icon: FileBarChart, roles: TENANT_ROLES, enabled: true },
  { label: 'Notificaciones', href: '/notificaciones', icon: Bell, roles: TENANT_ROLES, enabled: true },
  { label: 'Usuarios y Roles', href: '/usuarios', icon: Users, roles: ADMIN_ROLES, enabled: true },
  { label: 'Chatbot', href: '/chatbot', icon: Bot, roles: TENANT_ROLES, enabled: true },
  { label: 'Configuración / Perfil', href: '/perfil', icon: Settings, roles: TENANT_ROLES, enabled: true },
];

/**
 * Menú del ámbito plataforma (solo A0). El Chatbot aparece porque la matriz
 * le da "C" en el chatbot privilegiado (el tenant-aware le marca "—"); es la
 * misma ruta, que cambia de comportamiento según el rol (Sección K).
 */
export const PLATFORM_NAV_ITEMS: readonly NavItem[] = [
  // Se llama "Dashboard" porque es lo que significa para él, pero apunta a
  // /plataforma: /dashboard filtra por tenantId y el suyo es null.
  { label: 'Dashboard', href: '/plataforma', icon: LayoutDashboard, roles: ['superadmin'], enabled: true },
  { label: 'Gestión de Tenants', href: '/gestion-tenants', icon: ServerCog, roles: ['superadmin'], enabled: true },
  { label: 'Soporte', href: '/soporte', icon: LifeBuoy, roles: ['superadmin'], enabled: true },
  { label: 'Chatbot', href: '/chatbot', icon: Bot, roles: ['superadmin'], enabled: true },
  { label: 'Configuración / Perfil', href: '/perfil', icon: Settings, roles: ['superadmin'], enabled: true },
  { label: 'Planes de prueba', href: '#', icon: FlaskConical, roles: ['superadmin'], enabled: false },
];

/** Rutas del ámbito tenant: quien no pertenece a un tenant no tiene nada que hacer aquí. */
const TENANT_SCOPED_PREFIXES = [
  '/dashboard',
  '/perfil-empresa',
  '/matriz-legal',
  '/obligaciones',
  '/calendario',
  '/auditorias',
  '/no-conformidades',
  '/catalogo-normativo',
  '/gestores',
  '/planes-accion',
  '/reportes',
  '/notificaciones',
  '/usuarios',
] as const;

/** Rutas del ámbito plataforma: solo el Superadmin. */
const PLATFORM_SCOPED_PREFIXES = ['/plataforma', '/gestion-tenants', '/soporte'] as const;

export function esRutaDeTenant(pathname: string): boolean {
  return TENANT_SCOPED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function esRutaDePlataforma(pathname: string): boolean {
  return PLATFORM_SCOPED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Menú que corresponde al rol. */
export function navItemsParaRol(role: Role): readonly NavItem[] {
  if (role === 'superadmin') return PLATFORM_NAV_ITEMS;
  return TENANT_NAV_ITEMS.filter((item) => item.roles.includes(role));
}

/**
 * Pantalla de inicio de cada rol. El Superadmin no aterriza en /dashboard
 * porque ese dashboard filtra por `tenantId` y para él siempre saldría vacío;
 * su equivalente es /plataforma, el dashboard consolidado del negocio.
 */
export function rutaInicialParaRol(role: Role): string {
  if (role === 'superadmin') return '/plataforma';
  if (role === 'cliente_invitado') return '/crear-ticket';
  return '/dashboard';
}
