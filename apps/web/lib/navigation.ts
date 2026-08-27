import { FEATURE_FLAGS, type Role } from '@ambienta/shared';
import {
  AlertTriangle,
  Bell,
  BookMarked,
  Bot,
  Building,
  Building2,
  CalendarDays,
  ClipboardList,
  FileBarChart,
  FileWarning,
  FolderOpen,
  FlaskConical,
  History,
  LayoutDashboard,
  Leaf,
  LifeBuoy,
  ScrollText,
  ServerCog,
  Settings,
  ShieldAlert,
  Users,
  Wrench,
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
  // Va junto a Matriz Legal y no al final: es el detalle del numero del
  // tablero, y se busca cuando ese numero preocupa.
  { label: 'Incumplimientos', href: '/incumplimientos', icon: FileWarning, roles: TENANT_ROLES, enabled: true },
  { label: 'Auditorías', href: '/auditorias', icon: ShieldAlert, roles: TENANT_ROLES, enabled: true },
  { label: 'No Conformidades', href: '/no-conformidades', icon: ShieldAlert, roles: TENANT_ROLES, enabled: true },
  ...(FEATURE_FLAGS.matricesIso
    ? ([
        { label: 'Aspectos Ambientales', href: '/aspectos-ambientales', icon: Leaf, roles: TENANT_ROLES, enabled: true },
        { label: 'Riesgos y Oportunidades', href: '/riesgos-oportunidades', icon: AlertTriangle, roles: TENANT_ROLES, enabled: true },
        { label: 'Equipos Regulados', href: '/equipos-regulados', icon: Wrench, roles: TENANT_ROLES, enabled: true },
      ] satisfies NavItem[])
    : []),
  // Va antes del catalogo y despues de las auditorias: es donde se guarda lo
  // que respalda todo lo de arriba. La evidencia de una auditoria y el
  // procedimiento que se cita en una no conformidad viven aca.
  { label: 'Documentos', href: '/documentos', icon: FolderOpen, roles: TENANT_ROLES, enabled: true },
  { label: 'Catálogo Normativo', href: '/catalogo-normativo', icon: BookMarked, roles: TENANT_ROLES, enabled: true },
  { label: 'Gestores', href: '/gestores', icon: Building2, roles: ['gestor'], enabled: true },
  { label: 'Reportes', href: '/reportes', icon: FileBarChart, roles: TENANT_ROLES, enabled: true },
  { label: 'Notificaciones', href: '/notificaciones', icon: Bell, roles: TENANT_ROLES, enabled: true },
  { label: 'Usuarios y Roles', href: '/usuarios', icon: Users, roles: ADMIN_ROLES, enabled: true },
  { label: 'Chatbot', href: '/chatbot', icon: Bot, roles: TENANT_ROLES, enabled: true },
  // Historial/audit log (RF-32, RNF-25): lo ven todos los roles de tenant.
  // La matriz no lo lista como módulo aparte porque es transversal — es el
  // registro de lo que cada uno hizo en los módulos que sí le corresponden.
  { label: 'Historial', href: '/historial', icon: History, roles: TENANT_ROLES, enabled: true },
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
  // Contraparte de "Usuarios y Roles": esa administra la gente de una empresa,
  // esta la del equipo de Ambienta.
  { label: 'Equipo de plataforma', href: '/equipo', icon: Users, roles: ['superadmin'], enabled: true },
  // Clasificar normativa es ambito plataforma, no de una empresa: `norm_sectors`
  // no lleva `tenant_id`, asi que una clasificacion errada se propaga a TODAS
  // las empresas del sector. Por eso vive aca y no en el catalogo normativo.
  { label: 'Clasificación normativa', href: '/clasificacion-normativa', icon: BookMarked, roles: ['superadmin'], enabled: true },
  { label: 'Soporte', href: '/soporte', icon: LifeBuoy, roles: ['superadmin'], enabled: true },
  { label: 'Chatbot', href: '/chatbot', icon: Bot, roles: ['superadmin'], enabled: true },
  { label: 'Historial', href: '/historial', icon: History, roles: ['superadmin'], enabled: true },
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
  '/incumplimientos',
  '/auditorias',
  '/no-conformidades',
  '/documentos',
  '/aspectos-ambientales',
  '/riesgos-oportunidades',
  '/equipos-regulados',
  '/catalogo-normativo',
  '/gestores',
  '/planes-accion',
  '/reportes',
  '/notificaciones',
  '/usuarios',
] as const;

/** Rutas del ámbito plataforma: solo el Superadmin. */
const PLATFORM_SCOPED_PREFIXES = [
  '/plataforma',
  '/gestion-tenants',
  '/equipo',
  '/soporte',
  '/clasificacion-normativa',
] as const;

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
