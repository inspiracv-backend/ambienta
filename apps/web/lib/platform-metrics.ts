import type { SupportTicket, Tenant, User } from '@ambienta/shared';
import { diasParaVencimiento } from '@ambienta/shared';

export interface PlatformMetrics {
  tenantsActivos: number;
  tenantsSuspendidos: number;
  tenantsTotal: number;
  gestores: number;
  demos: number;
  usuariosTotal: number;
  ticketsAbiertos: number;
  ticketsEnProgreso: number;
  /** Tenants que aún no completaron el Perfil Empresa (RF-10): no pueden operar. */
  perfilesIncompletos: Tenant[];
  /** Tenants con ≥90% del límite de usuarios contratado. */
  cercaDelLimite: Array<{ tenant: Tenant; usuarios: number; porcentaje: number }>;
  /** Suscripciones que vencen pronto o ya vencieron, las más urgentes primero. */
  suscripcionesPorVencer: Array<{ tenant: Tenant; diasRestantes: number }>;
}

const UMBRAL_LIMITE = 0.9;

/**
 * Ventana de aviso de vencimiento. Una demo dura 10 días por defecto, así que
 * avisar con 15 cubre tanto la demo completa como el mes previo a la
 * renovación de un contrato anual.
 */
export const DIAS_AVISO_VENCIMIENTO = 15;

/**
 * Métricas de la plataforma para el Superadmin (A0).
 *
 * La matriz de permisos le asigna "Dashboard consolidado: C (global)", pero
 * hasta ahora aterrizaba en una tabla de tenants sin ningún número agregado.
 * El dashboard del tenant no le sirve: filtra por `tenantId` y el suyo es
 * null.
 *
 * Dos señales no son solo estadística, son trabajo pendiente concreto:
 * - `perfilesIncompletos`: un tenant sin Perfil Empresa está bloqueado por
 *   `PerfilEmpresaGate` (RF-10) y no puede usar el producto. Es la principal
 *   causa de un cliente que "no está usando el sistema" tras el onboarding.
 * - `cercaDelLimite`: RF-81 le da al Superadmin el control de los límites de
 *   usuarios; avisar antes de que el cliente choque con el tope evita el
 *   ticket de soporte.
 */
export function computePlatformMetrics(
  tenants: Tenant[],
  users: User[],
  tickets: SupportTicket[],
  ahora: Date = new Date(),
): PlatformMetrics {
  const usuariosPorTenant = users.reduce<Record<string, number>>((acc, u) => {
    if (u.tenantId) acc[u.tenantId] = (acc[u.tenantId] ?? 0) + 1;
    return acc;
  }, {});

  const cercaDelLimite = tenants
    .map((tenant) => {
      const usuarios = usuariosPorTenant[tenant.id] ?? 0;
      const limite = tenant.suscripcion.limiteUsuarios;
      return { tenant, usuarios, porcentaje: limite > 0 ? usuarios / limite : 0 };
    })
    .filter((t) => t.porcentaje >= UMBRAL_LIMITE)
    .sort((a, b) => b.porcentaje - a.porcentaje);

  const suscripcionesPorVencer = tenants
    .map((tenant) => ({ tenant, diasRestantes: diasParaVencimiento(tenant.suscripcion, ahora) }))
    .filter((t) => t.diasRestantes <= DIAS_AVISO_VENCIMIENTO)
    .sort((a, b) => a.diasRestantes - b.diasRestantes);

  return {
    tenantsActivos: tenants.filter((t) => t.estado === 'activo').length,
    tenantsSuspendidos: tenants.filter((t) => t.estado === 'suspendido').length,
    tenantsTotal: tenants.length,
    gestores: tenants.filter((t) => t.esGestor).length,
    demos: tenants.filter((t) => t.suscripcion.plan === 'demo').length,
    // Los usuarios de plataforma (Superadmin, tenantId null) no son clientes.
    usuariosTotal: users.filter((u) => u.tenantId !== null).length,
    ticketsAbiertos: tickets.filter((t) => t.estado === 'abierto').length,
    ticketsEnProgreso: tickets.filter((t) => t.estado === 'en_progreso').length,
    perfilesIncompletos: tenants.filter((t) => !t.perfilEmpresaCompleto),
    cercaDelLimite,
    suscripcionesPorVencer,
  };
}
