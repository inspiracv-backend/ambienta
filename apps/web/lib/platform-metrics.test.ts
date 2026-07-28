import { describe, expect, it } from 'vitest';
import type { SupportTicket, Tenant, User } from '@ambienta/shared';
import { computePlatformMetrics } from './platform-metrics';

function tenant(over: Partial<Tenant> & { id: string }): Tenant {
  return {
    nombre: `Tenant ${over.id}`,
    rut: '76.000.000-0',
    esGestor: false,
    perfilEmpresaCompleto: true,
    estado: 'activo',
    limiteUsuarios: 10,
    modulosActivos: [],
    plants: [],
    ...over,
  } as Tenant;
}

function user(over: Partial<User> & { id: string }): User {
  return {
    tenantId: 'tenant-1',
    nombre: 'Usuario',
    email: 'u@e.cl',
    role: 'usuario_interno',
    plantIds: [],
    departamentoId: null,
    estado: 'activo',
    ultimaActividad: '2026-07-01T00:00:00.000Z',
    ...over,
  } as User;
}

function ticket(over: Partial<SupportTicket> & { id: string }): SupportTicket {
  return {
    numero: 'T-001',
    tenantId: 'tenant-1',
    tipoSolicitud: 'consulta',
    asunto: 'Asunto',
    descripcion: 'Descripción',
    estado: 'abierto',
    fecha: '2026-07-01T00:00:00.000Z',
    visibleParaCliente: true,
    correcciones: [],
    ...over,
  } as SupportTicket;
}

describe('computePlatformMetrics — conteos', () => {
  it('separa tenants activos de suspendidos', () => {
    const m = computePlatformMetrics(
      [
        tenant({ id: 't1', estado: 'activo' }),
        tenant({ id: 't2', estado: 'activo' }),
        tenant({ id: 't3', estado: 'suspendido' }),
      ],
      [],
      [],
    );
    expect(m.tenantsActivos).toBe(2);
    expect(m.tenantsSuspendidos).toBe(1);
    expect(m.tenantsTotal).toBe(3);
  });

  it('cuenta gestores', () => {
    const m = computePlatformMetrics(
      [tenant({ id: 't1', esGestor: true }), tenant({ id: 't2', esGestor: false })],
      [],
      [],
    );
    expect(m.gestores).toBe(1);
  });

  it('no cuenta a los usuarios de plataforma como usuarios de cliente', () => {
    // El Superadmin tiene tenantId null: no es un usuario facturable.
    const m = computePlatformMetrics(
      [tenant({ id: 't1' })],
      [user({ id: 'u1' }), user({ id: 'u2' }), user({ id: 'super', tenantId: null, role: 'superadmin' })],
      [],
    );
    expect(m.usuariosTotal).toBe(2);
  });

  it('separa tickets abiertos de los que están en progreso', () => {
    const m = computePlatformMetrics(
      [],
      [],
      [
        ticket({ id: 'a', estado: 'abierto' }),
        ticket({ id: 'b', estado: 'abierto' }),
        ticket({ id: 'c', estado: 'en_progreso' }),
        ticket({ id: 'd', estado: 'cerrado' }),
      ],
    );
    expect(m.ticketsAbiertos).toBe(2);
    expect(m.ticketsEnProgreso).toBe(1);
  });
});

describe('computePlatformMetrics — señales accionables', () => {
  it('detecta tenants bloqueados por Perfil Empresa incompleto (RF-10)', () => {
    const m = computePlatformMetrics(
      [
        tenant({ id: 't1', perfilEmpresaCompleto: true }),
        tenant({ id: 'bloqueado', perfilEmpresaCompleto: false }),
      ],
      [],
      [],
    );
    expect(m.perfilesIncompletos.map((t) => t.id)).toEqual(['bloqueado']);
  });

  it('avisa de los tenants que llegan al 90% de su límite de usuarios', () => {
    const m = computePlatformMetrics(
      [tenant({ id: 'lleno', limiteUsuarios: 10 })],
      Array.from({ length: 9 }, (_, i) => user({ id: `u${i}`, tenantId: 'lleno' })),
      [],
    );
    expect(m.cercaDelLimite).toHaveLength(1);
    expect(m.cercaDelLimite[0]!.porcentaje).toBeCloseTo(0.9);
  });

  it('no avisa por debajo del umbral', () => {
    const m = computePlatformMetrics(
      [tenant({ id: 'holgado', limiteUsuarios: 10 })],
      Array.from({ length: 5 }, (_, i) => user({ id: `u${i}`, tenantId: 'holgado' })),
      [],
    );
    expect(m.cercaDelLimite).toHaveLength(0);
  });

  it('ordena los más críticos primero', () => {
    const m = computePlatformMetrics(
      [tenant({ id: 'al-90', limiteUsuarios: 10 }), tenant({ id: 'excedido', limiteUsuarios: 2 })],
      [
        ...Array.from({ length: 9 }, (_, i) => user({ id: `a${i}`, tenantId: 'al-90' })),
        ...Array.from({ length: 3 }, (_, i) => user({ id: `b${i}`, tenantId: 'excedido' })),
      ],
      [],
    );
    expect(m.cercaDelLimite[0]!.tenant.id).toBe('excedido');
  });

  it('no divide por cero cuando el límite es 0', () => {
    const m = computePlatformMetrics([tenant({ id: 't1', limiteUsuarios: 0 })], [user({ id: 'u1' })], []);
    expect(m.cercaDelLimite).toHaveLength(0);
  });

  it('devuelve ceros con la plataforma vacía', () => {
    const m = computePlatformMetrics([], [], []);
    expect(m.tenantsTotal).toBe(0);
    expect(m.usuariosTotal).toBe(0);
    expect(m.perfilesIncompletos).toHaveLength(0);
    expect(m.cercaDelLimite).toHaveLength(0);
  });
});
