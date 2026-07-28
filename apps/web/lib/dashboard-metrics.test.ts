import { describe, expect, it } from 'vitest';
import type { NonConformity, Obligation, Plant } from '@ambienta/shared';
import { computePlantMetrics } from './dashboard-metrics';

/**
 * El dashboard multi-planta (S-07, RF-55) es lo primero que ve el Admin
 * Empresa. Estos tests fijan que las métricas se calculen por planta y no se
 * mezclen entre plantas ni entre tenants — un cruce ahí sería una fuga de
 * datos visible.
 */

function planta(id: string, tenantId = 'tenant-1'): Plant {
  return { id, tenantId, nombre: `Planta ${id}`, comuna: 'Comuna', region: 'Región' } as Plant;
}

function obligacion(over: Partial<Obligation> & { id: string; plantId: string }): Obligation {
  return {
    tenantId: 'tenant-1',
    nombre: 'Obligación',
    estado: 'vigente',
    proximoVencimiento: '2026-12-31T00:00:00.000Z',
    ...over,
  } as Obligation;
}

function noConformidad(over: Partial<NonConformity> & { id: string }): NonConformity {
  return { tenantId: 'tenant-1', estado: 'abierta', ...over } as NonConformity;
}

describe('computePlantMetrics', () => {
  it('calcula el % de cumplimiento como vigentes sobre el total de la planta', () => {
    const p = planta('p1');
    const [m] = computePlantMetrics(
      [p],
      [
        obligacion({ id: 'o1', plantId: 'p1', estado: 'vigente' }),
        obligacion({ id: 'o2', plantId: 'p1', estado: 'vigente' }),
        obligacion({ id: 'o3', plantId: 'p1', estado: 'vencida' }),
        obligacion({ id: 'o4', plantId: 'p1', estado: 'sin_evidencia' }),
      ],
      [],
    );
    expect(m!.cumplimientoPct).toBe(0.5);
    expect(m!.incumplimientos).toBe(2);
  });

  it('no mezcla obligaciones de otras plantas', () => {
    const metrics = computePlantMetrics(
      [planta('p1'), planta('p2')],
      [
        obligacion({ id: 'o1', plantId: 'p1', estado: 'vencida' }),
        obligacion({ id: 'o2', plantId: 'p2', estado: 'vigente' }),
      ],
      [],
    );
    expect(metrics[0]!.incumplimientos).toBe(1);
    expect(metrics[1]!.incumplimientos).toBe(0);
    expect(metrics[1]!.cumplimientoPct).toBe(1);
  });

  it('devuelve 0% en una planta sin obligaciones, sin dividir por cero', () => {
    const [m] = computePlantMetrics([planta('p1')], [], []);
    expect(m!.cumplimientoPct).toBe(0);
    expect(m!.incumplimientos).toBe(0);
    expect(m!.proximoVencimiento).toBeNull();
  });

  it('elige como próximo vencimiento el más cercano entre los no vigentes', () => {
    const [m] = computePlantMetrics(
      [planta('p1')],
      [
        obligacion({ id: 'lejana', plantId: 'p1', estado: 'vencida', proximoVencimiento: '2026-12-01T00:00:00.000Z' }),
        obligacion({ id: 'cercana', plantId: 'p1', estado: 'vencida', proximoVencimiento: '2026-08-01T00:00:00.000Z' }),
        // Una vigente más cercana no debe ganar: no es lo que hay que atender.
        obligacion({ id: 'vigente', plantId: 'p1', estado: 'vigente', proximoVencimiento: '2026-07-01T00:00:00.000Z' }),
      ],
      [],
    );
    expect(m!.proximoVencimiento?.id).toBe('cercana');
  });

  it('no muta el arreglo de obligaciones que recibe', () => {
    // El orden importa fuera de aquí: las listas se renderizan tal cual.
    const obligaciones = [
      obligacion({ id: 'b', plantId: 'p1', estado: 'vencida', proximoVencimiento: '2026-12-01T00:00:00.000Z' }),
      obligacion({ id: 'a', plantId: 'p1', estado: 'vencida', proximoVencimiento: '2026-08-01T00:00:00.000Z' }),
    ];
    computePlantMetrics([planta('p1')], obligaciones, []);
    expect(obligaciones.map((o) => o.id)).toEqual(['b', 'a']);
  });

  it('cuenta no conformidades abiertas del tenant y excluye las cerradas', () => {
    const [m] = computePlantMetrics(
      [planta('p1', 'tenant-1')],
      [],
      [
        noConformidad({ id: 'nc1', estado: 'abierta' }),
        noConformidad({ id: 'nc2', estado: 'en_tratamiento' }),
        noConformidad({ id: 'nc3', estado: 'cerrada' }),
      ],
    );
    expect(m!.noConformidadesActivas).toBe(2);
  });

  it('no cuenta no conformidades de otro tenant', () => {
    const [m] = computePlantMetrics(
      [planta('p1', 'tenant-1')],
      [],
      [
        noConformidad({ id: 'nc1', estado: 'abierta' }),
        noConformidad({ id: 'ajena', tenantId: 'tenant-2', estado: 'abierta' }),
      ],
    );
    expect(m!.noConformidadesActivas).toBe(1);
  });

  it('devuelve una métrica por planta, en el mismo orden', () => {
    const metrics = computePlantMetrics([planta('p1'), planta('p2'), planta('p3')], [], []);
    expect(metrics.map((m) => m.plant.id)).toEqual(['p1', 'p2', 'p3']);
  });
});
