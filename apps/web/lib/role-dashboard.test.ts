import { describe, expect, it } from 'vitest';
import type { Contrato, PlanAccion, SubTenant, User } from '@ambienta/shared';
import { computeResumenGestor, computeResumenUsuarioInterno, DIAS_AVISO_CONTRATO } from './role-dashboard';

/** Fecha fija: los cálculos dependen de "hoy" y un test con `new Date()` real es inestable. */
const AHORA = new Date('2026-07-28T12:00:00.000Z');
const DIA = 86_400_000;

function enDias(dias: number): string {
  return new Date(AHORA.getTime() + dias * DIA).toISOString();
}

function subTenant(over: Partial<SubTenant> & { id: string }): SubTenant {
  return {
    gestorTenantId: 'tenant-2',
    nombre: `Cliente ${over.id}`,
    rut: '76.000.000-0',
    estado: 'activo',
    contactos: [],
    ...over,
  } as SubTenant;
}

function contrato(over: Partial<Contrato> & { id: string; subTenantId: string }): Contrato {
  return {
    nombre: 'Contrato de gestión',
    fechaInicio: enDias(-365),
    fechaTermino: enDias(365),
    camposCustom: {},
    ...over,
  } as Contrato;
}

function plan(over: Partial<PlanAccion> & { id: string }): PlanAccion {
  return {
    tenantId: 'tenant-1',
    origenTipo: 'no_conformidad',
    origenId: 'nc-1',
    origenLabel: 'NC-001',
    titulo: 'Plan',
    responsableId: 'user-interno',
    fechaLimite: enDias(10),
    estado: 'abierto',
    tareas: [],
    ...over,
  } as PlanAccion;
}

const usuario = { id: 'user-interno', tenantId: 'tenant-1' } as User;

describe('computeResumenGestor', () => {
  it('separa sub-tenants activos de inactivos', () => {
    const r = computeResumenGestor(
      [subTenant({ id: 's1' }), subTenant({ id: 's2' }), subTenant({ id: 's3', estado: 'inactivo' })],
      [],
      AHORA,
    );
    expect(r.subTenantsActivos).toBe(2);
    expect(r.subTenantsInactivos).toBe(1);
  });

  it('avisa de los contratos que vencen dentro de la ventana', () => {
    const r = computeResumenGestor(
      [subTenant({ id: 's1' })],
      [contrato({ id: 'c1', subTenantId: 's1', fechaTermino: enDias(10) })],
      AHORA,
    );
    expect(r.contratosPorVencer).toHaveLength(1);
    expect(r.contratosPorVencer[0]!.diasRestantes).toBe(10);
  });

  it('no avisa de contratos que vencen más allá de la ventana', () => {
    const r = computeResumenGestor(
      [subTenant({ id: 's1' })],
      [contrato({ id: 'c1', subTenantId: 's1', fechaTermino: enDias(DIAS_AVISO_CONTRATO + 5) })],
      AHORA,
    );
    expect(r.contratosPorVencer).toHaveLength(0);
  });

  it('cuenta los vencidos aparte y no los mezcla con los por vencer', () => {
    // Un contrato ya vencido no "está por vencer": exige otra acción.
    const r = computeResumenGestor(
      [subTenant({ id: 's1' })],
      [
        contrato({ id: 'vencido', subTenantId: 's1', fechaTermino: enDias(-5) }),
        contrato({ id: 'porVencer', subTenantId: 's1', fechaTermino: enDias(5) }),
      ],
      AHORA,
    );
    expect(r.contratosVencidos).toBe(1);
    expect(r.contratosPorVencer).toHaveLength(1);
    expect(r.contratosPorVencer[0]!.contrato.id).toBe('porVencer');
    expect(r.contratosVigentes).toBe(1);
  });

  it('ordena los más urgentes primero', () => {
    const r = computeResumenGestor(
      [subTenant({ id: 's1' })],
      [
        contrato({ id: 'en20', subTenantId: 's1', fechaTermino: enDias(20) }),
        contrato({ id: 'en3', subTenantId: 's1', fechaTermino: enDias(3) }),
        contrato({ id: 'en12', subTenantId: 's1', fechaTermino: enDias(12) }),
      ],
      AHORA,
    );
    expect(r.contratosPorVencer.map((c) => c.contrato.id)).toEqual(['en3', 'en12', 'en20']);
  });

  it('resuelve el sub-tenant de cada contrato para poder nombrarlo', () => {
    const r = computeResumenGestor(
      [subTenant({ id: 's1', nombre: 'Minera Norte' })],
      [contrato({ id: 'c1', subTenantId: 's1', fechaTermino: enDias(7) })],
      AHORA,
    );
    expect(r.contratosPorVencer[0]!.subTenant?.nombre).toBe('Minera Norte');
  });

  it('no rompe si el contrato apunta a un sub-tenant que ya no existe', () => {
    const r = computeResumenGestor([], [contrato({ id: 'c1', subTenantId: 'borrado', fechaTermino: enDias(7) })], AHORA);
    expect(r.contratosPorVencer[0]!.subTenant).toBeUndefined();
  });
});

describe('computeResumenUsuarioInterno', () => {
  it('solo trae los planes donde el usuario es responsable', () => {
    const r = computeResumenUsuarioInterno(
      [
        plan({ id: 'mio' }),
        plan({ id: 'de-otro', responsableId: 'user-admin-empresa' }),
        plan({ id: 'sin-responsable', responsableId: undefined }),
      ],
      usuario,
      AHORA,
    );
    expect(r.planesAsignados.map((p) => p.id)).toEqual(['mio']);
  });

  it('no cruza planes de otro tenant', () => {
    const r = computeResumenUsuarioInterno(
      [plan({ id: 'mio' }), plan({ id: 'otro-tenant', tenantId: 'tenant-2' })],
      usuario,
      AHORA,
    );
    expect(r.planesAsignados.map((p) => p.id)).toEqual(['mio']);
  });

  it('detecta los atrasados', () => {
    const r = computeResumenUsuarioInterno(
      [plan({ id: 'atrasado', fechaLimite: enDias(-3) }), plan({ id: 'a-tiempo', fechaLimite: enDias(3) })],
      usuario,
      AHORA,
    );
    expect(r.atrasados.map((p) => p.id)).toEqual(['atrasado']);
  });

  it('no cuenta como atrasado un plan ya cerrado', () => {
    // Cerrado fuera de plazo sigue estando cerrado: no es trabajo pendiente.
    const r = computeResumenUsuarioInterno(
      [plan({ id: 'cerrado-tarde', fechaLimite: enDias(-10), estado: 'cerrado' })],
      usuario,
      AHORA,
    );
    expect(r.atrasados).toHaveLength(0);
  });

  it('trae los que vencen dentro de la próxima semana', () => {
    const r = computeResumenUsuarioInterno(
      [
        plan({ id: 'en2', fechaLimite: enDias(2) }),
        plan({ id: 'en20', fechaLimite: enDias(20) }),
        plan({ id: 'atrasado', fechaLimite: enDias(-1) }),
      ],
      usuario,
      AHORA,
    );
    expect(r.proximos.map((p) => p.id)).toEqual(['en2']);
  });

  it('ordena atrasados y próximos por urgencia', () => {
    const r = computeResumenUsuarioInterno(
      [
        plan({ id: 'atraso-corto', fechaLimite: enDias(-2) }),
        plan({ id: 'atraso-largo', fechaLimite: enDias(-15) }),
        plan({ id: 'proximo-6', fechaLimite: enDias(6) }),
        plan({ id: 'proximo-1', fechaLimite: enDias(1) }),
      ],
      usuario,
      AHORA,
    );
    expect(r.atrasados.map((p) => p.id)).toEqual(['atraso-largo', 'atraso-corto']);
    expect(r.proximos.map((p) => p.id)).toEqual(['proximo-1', 'proximo-6']);
  });

  it('suma las tareas pendientes de todos sus planes', () => {
    const r = computeResumenUsuarioInterno(
      [
        plan({
          id: 'p1',
          tareas: [
            { id: 't1', titulo: 'A', hecha: true },
            { id: 't2', titulo: 'B', hecha: false },
          ],
        }),
        plan({ id: 'p2', tareas: [{ id: 't3', titulo: 'C', hecha: false }] }),
      ],
      usuario,
      AHORA,
    );
    expect(r.tareasTotales).toBe(3);
    expect(r.tareasPendientes).toBe(2);
  });

  it('devuelve ceros cuando no tiene nada asignado', () => {
    const r = computeResumenUsuarioInterno([], usuario, AHORA);
    expect(r.planesAsignados).toHaveLength(0);
    expect(r.tareasPendientes).toBe(0);
  });
});
