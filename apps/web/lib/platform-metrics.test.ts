import { describe, expect, it } from 'vitest';
import type { SupportTicket, Tenant, User } from '@ambienta/shared';
import { computePlatformMetrics } from './platform-metrics';

/** Fecha fija: las métricas dependen de "hoy" y `new Date()` haría el test inestable. */
const AHORA = new Date('2026-07-29T12:00:00.000Z');

function enDias(dias: number): string {
  return new Date(AHORA.getTime() + dias * 86_400_000).toISOString();
}

function tenant(
  over: Partial<Omit<Tenant, 'suscripcion'>> & { id: string; limiteUsuarios?: number; diasRestantes?: number; plan?: 'demo' | 'contrato' },
): Tenant {
  const { limiteUsuarios = 10, diasRestantes = 200, plan = 'contrato', ...resto } = over;
  return {
    nombre: `Tenant ${over.id}`,
    identificacion: { tipo: 'RUT', numero: '76.000.000-0' },
    pais: 'CL',
    sector: 'Industrial',
    certificaciones: [],
    esGestor: false,
    perfilEmpresaCompleto: true,
    estado: 'activo',
    suscripcion: {
      plan,
      fechaInicio: enDias(-100),
      fechaTermino: enDias(diasRestantes),
      limiteUsuarios,
    },
    modulosActivos: [],
    plants: [],
    ...resto,
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
      AHORA,
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
      AHORA,
    );
    expect(m.gestores).toBe(1);
  });

  it('no cuenta a los usuarios de plataforma como usuarios de cliente', () => {
    // El Superadmin tiene tenantId null: no es un usuario facturable.
    const m = computePlatformMetrics(
      [tenant({ id: 't1' })],
      [user({ id: 'u1' }), user({ id: 'u2' }), user({ id: 'super', tenantId: null, role: 'superadmin' })],
      [],
      AHORA,
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
      AHORA,
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
      AHORA,
    );
    expect(m.perfilesIncompletos.map((t) => t.id)).toEqual(['bloqueado']);
  });

  it('avisa de los tenants que llegan al 90% de su límite de usuarios', () => {
    const m = computePlatformMetrics(
      [tenant({ id: 'lleno', limiteUsuarios: 10 })],
      Array.from({ length: 9 }, (_, i) => user({ id: `u${i}`, tenantId: 'lleno' })),
      [],
      AHORA,
    );
    expect(m.cercaDelLimite).toHaveLength(1);
    expect(m.cercaDelLimite[0]!.porcentaje).toBeCloseTo(0.9);
  });

  it('no avisa por debajo del umbral', () => {
    const m = computePlatformMetrics(
      [tenant({ id: 'holgado', limiteUsuarios: 10 })],
      Array.from({ length: 5 }, (_, i) => user({ id: `u${i}`, tenantId: 'holgado' })),
      [],
      AHORA,
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
      AHORA,
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
    expect(m.suscripcionesPorVencer).toHaveLength(0);
  });
});

describe('computePlatformMetrics — suscripciones', () => {
  it('cuenta las demos aparte de los contratos', () => {
    const m = computePlatformMetrics(
      [tenant({ id: 'd1', plan: 'demo' }), tenant({ id: 'c1', plan: 'contrato' })],
      [],
      [],
      AHORA,
    );
    expect(m.demos).toBe(1);
  });

  it('avisa de lo que vence dentro de la ventana', () => {
    // Una demo de 10 días entra completa en la ventana de aviso de 15.
    const m = computePlatformMetrics(
      [tenant({ id: 'porVencer', plan: 'demo', diasRestantes: 3 }), tenant({ id: 'holgado', diasRestantes: 200 })],
      [],
      [],
      AHORA,
    );
    expect(m.suscripcionesPorVencer.map((s) => s.tenant.id)).toEqual(['porVencer']);
  });

  it('incluye las ya vencidas, con días negativos', () => {
    // Una suscripción vencida es más urgente que una por vencer: el cliente
    // ya perdió el servicio.
    const m = computePlatformMetrics([tenant({ id: 'vencida', diasRestantes: -5 })], [], [], AHORA);
    expect(m.suscripcionesPorVencer[0]!.diasRestantes).toBeLessThan(0);
  });

  it('ordena las más urgentes primero', () => {
    const m = computePlatformMetrics(
      [
        tenant({ id: 'en10', diasRestantes: 10 }),
        tenant({ id: 'vencida', diasRestantes: -3 }),
        tenant({ id: 'en2', diasRestantes: 2 }),
      ],
      [],
      [],
      AHORA,
    );
    expect(m.suscripcionesPorVencer.map((s) => s.tenant.id)).toEqual(['vencida', 'en2', 'en10']);
  });
});
