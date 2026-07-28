import type { Contrato, PlanAccion, SubTenant, User } from '@ambienta/shared';

const DIAS_MS = 86_400_000;

export interface ResumenGestor {
  subTenantsActivos: number;
  subTenantsInactivos: number;
  contratosVigentes: number;
  /** Contratos que vencen dentro de la ventana de aviso: hay que renovarlos. */
  contratosPorVencer: Array<{ contrato: Contrato; subTenant: SubTenant | undefined; diasRestantes: number }>;
  contratosVencidos: number;
}

/** Un mes de aviso: renegociar un contrato de gestión de residuos no se hace en un día. */
export const DIAS_AVISO_CONTRATO = 30;

/**
 * Resumen del Gestor (A4).
 *
 * Su negocio no son las obligaciones propias sino la cartera de clientes:
 * un contrato vencido significa que está prestando servicio sin respaldo
 * formal, y el Contrato es la entidad de la que cuelga todo el sub-tenant
 * (RF-66). Por eso lo que se destaca es el vencimiento, no el conteo.
 */
export function computeResumenGestor(
  subTenants: SubTenant[],
  contratos: Contrato[],
  ahora: Date = new Date(),
): ResumenGestor {
  const hoy = ahora.getTime();
  const limiteAviso = hoy + DIAS_AVISO_CONTRATO * DIAS_MS;

  const porVencer = contratos
    .map((contrato) => {
      const termino = new Date(contrato.fechaTermino).getTime();
      return {
        contrato,
        subTenant: subTenants.find((s) => s.id === contrato.subTenantId),
        diasRestantes: Math.ceil((termino - hoy) / DIAS_MS),
        termino,
      };
    })
    .filter((c) => c.termino >= hoy && c.termino <= limiteAviso)
    .sort((a, b) => a.termino - b.termino)
    .map(({ contrato, subTenant, diasRestantes }) => ({ contrato, subTenant, diasRestantes }));

  return {
    subTenantsActivos: subTenants.filter((s) => s.estado === 'activo').length,
    subTenantsInactivos: subTenants.filter((s) => s.estado === 'inactivo').length,
    contratosVigentes: contratos.filter((c) => new Date(c.fechaTermino).getTime() >= hoy).length,
    contratosPorVencer: porVencer,
    contratosVencidos: contratos.filter((c) => new Date(c.fechaTermino).getTime() < hoy).length,
  };
}

export interface ResumenUsuarioInterno {
  planesAsignados: PlanAccion[];
  /** Con fecha límite pasada y sin cerrar: son las que generan incumplimiento. */
  atrasados: PlanAccion[];
  /** Vencen dentro de la próxima semana. */
  proximos: PlanAccion[];
  tareasPendientes: number;
  tareasTotales: number;
}

const DIAS_PROXIMO = 7;

/**
 * Resumen del Usuario Interno (A2).
 *
 * RF-40 pide "vista de tareas asignadas por persona", y la matriz de permisos
 * le da las obligaciones "G (asignadas)" — no el panorama completo del tenant.
 * Mostrarle el mismo resumen ejecutivo que al Admin Empresa lo obliga a
 * buscar, entre todo lo de la empresa, qué le toca a él.
 */
export function computeResumenUsuarioInterno(
  planes: PlanAccion[],
  user: User,
  ahora: Date = new Date(),
): ResumenUsuarioInterno {
  const hoy = ahora.getTime();
  const limiteProximo = hoy + DIAS_PROXIMO * DIAS_MS;

  const asignados = planes.filter((p) => p.responsableId === user.id && p.tenantId === user.tenantId);
  const abiertos = asignados.filter((p) => p.estado !== 'cerrado');

  const tareasTotales = asignados.reduce((n, p) => n + p.tareas.length, 0);
  const tareasPendientes = asignados.reduce((n, p) => n + p.tareas.filter((t) => !t.hecha).length, 0);

  return {
    planesAsignados: asignados,
    atrasados: abiertos
      .filter((p) => new Date(p.fechaLimite).getTime() < hoy)
      .sort((a, b) => new Date(a.fechaLimite).getTime() - new Date(b.fechaLimite).getTime()),
    proximos: abiertos
      .filter((p) => {
        const t = new Date(p.fechaLimite).getTime();
        return t >= hoy && t <= limiteProximo;
      })
      .sort((a, b) => new Date(a.fechaLimite).getTime() - new Date(b.fechaLimite).getTime()),
    tareasPendientes,
    tareasTotales,
  };
}
