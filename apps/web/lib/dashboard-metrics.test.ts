import { describe, expect, it } from 'vitest';
import type { NonConformity, Obligation, Plant } from '@ambienta/shared';
import { computePlantMetrics, fromApiMetrics, type ApiDashboardMetrics } from './dashboard-metrics';

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

  it('una planta sin obligaciones no tiene porcentaje, y no divide por cero', () => {
    // **Esta prueba fijaba el error.** Afirmaba `toBe(0)`, y ese cero llegaba
    // hasta el tablero ejecutivo: dos de las tres plantas del seed no tienen
    // una sola evaluacion y aparecian en rojo, con "0 % de cumplimiento".
    //
    // La intencion original era buena —que no se divida por cero— y esa parte
    // se conserva. Lo que estaba mal era el valor con el que se cumplia.
    const [m] = computePlantMetrics([planta('p1')], [], []);
    expect(m!.cumplimientoPct).toBeNull();
    expect(m!.incumplimientos).toBe(0);
    expect(m!.proximoVencimiento).toBeNull();
  });

  it('con obligaciones y ninguna vigente el cero SI es un cero medido', () => {
    // El otro lado: distinguir "sin datos" no puede tapar el incumplimiento
    // real. Aca hay una obligacion y esta vencida — el cero corresponde.
    const [m] = computePlantMetrics(
      [planta('p1')],
      [obligacion({ id: 'o1', plantId: 'p1', estado: 'vencida' })],
      [],
    );
    expect(m!.cumplimientoPct).toBe(0);
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

/**
 * El adaptador es el punto donde dos vocabularios se cruzan: la API habla en
 * porcentaje y snake_case, la UI en fracción y camelCase. Un error acá se ve
 * como "7530% de cumplimiento" y no rompe nada, que es lo peligroso.
 */
function apiResponse(over: Partial<ApiDashboardMetrics> = {}): ApiDashboardMetrics {
  return {
    tenant_id: 'tenant-1',
    generated_at: '2026-08-05T12:00:00Z',
    global: {
      compliance_percentage: 0,
      articles_evaluated: 0,
      articles_non_compliant: 0,
      total_obligations: 0,
      nc_open: 0,
      obligations_upcoming: 0,
      obligations_overdue: 0,
    },
    critical_deadline: null,
    upcoming_deadlines: [],
    facilities: [],
    ...over,
  };
}

describe('fromApiMetrics', () => {
  it('convierte el porcentaje de la API (0-100) a la fracción que usa la UI (0-1)', () => {
    const vm = fromApiMetrics(
      apiResponse({ global: { ...apiResponse().global, compliance_percentage: 75.3 } }),
    );
    expect(vm.cumplimientoGlobal).toBeCloseTo(0.753);
  });

  it('convierte también el porcentaje de cada planta', () => {
    const vm = fromApiMetrics(
      apiResponse({
        facilities: [
          {
            facility_id: 'f1',
            name: 'Planta Norte',
            commune_code: 'Antofagasta',
            region_code: 'II',
            compliance_percentage: 80,
            non_compliant_count: 2,
            nc_open_count: 1,
            critical_deadline: null,
          },
        ],
      }),
    );
    expect(vm.plantas[0]!.cumplimientoPct).toBe(0.8);
    expect(vm.plantas[0]!.plant.nombre).toBe('Planta Norte');
    expect(vm.plantas[0]!.plant.comuna).toBe('Antofagasta');
  });

  it('marca como vencida una obligación con días negativos, sin mirar su status', () => {
    const vm = fromApiMetrics(
      apiResponse({
        critical_deadline: {
          obligation_id: 'o1',
          code: 'OBL-1',
          title: 'Declaración RETC',
          due_at: '2026-07-01T00:00:00Z',
          days_remaining: -5,
          status: 'open',
        },
      }),
    );
    expect(vm.proximoCritico!.estado).toBe('vencida');
    expect(vm.proximoCritico!.id).toBe('o1');
  });

  it('marca por_vencer dentro de 30 días y vigente más allá', () => {
    const base = {
      obligation_id: 'o1',
      code: 'OBL-1',
      title: 'X',
      due_at: '2026-09-01T00:00:00Z',
      status: 'open',
    };
    const cerca = fromApiMetrics(
      apiResponse({ critical_deadline: { ...base, days_remaining: 10 } }),
    );
    const lejos = fromApiMetrics(
      apiResponse({ critical_deadline: { ...base, days_remaining: 90 } }),
    );
    expect(cerca.proximoCritico!.estado).toBe('por_vencer');
    expect(lejos.proximoCritico!.estado).toBe('vigente');
  });

  it('trata un borrador como sin evidencia', () => {
    const vm = fromApiMetrics(
      apiResponse({
        critical_deadline: {
          obligation_id: 'o1',
          code: 'OBL-1',
          title: 'X',
          due_at: '2026-09-01T00:00:00Z',
          days_remaining: 60,
          status: 'draft',
        },
      }),
    );
    expect(vm.proximoCritico!.estado).toBe('sin_evidencia');
  });

  it('descarta un vencimiento sin fecha en vez de mostrar "Invalid Date"', () => {
    const vm = fromApiMetrics(
      apiResponse({
        critical_deadline: {
          obligation_id: 'o1',
          code: 'OBL-1',
          title: 'Sin fecha',
          due_at: null,
          days_remaining: null,
          status: 'open',
        },
      }),
    );
    expect(vm.proximoCritico).toBeNull();
  });

  it('un tenant sin datos da ceros, no NaN', () => {
    const vm = fromApiMetrics(apiResponse());
    expect(vm.cumplimientoGlobal).toBe(0);
    expect(vm.ncAbiertas).toBe(0);
    expect(vm.plantas).toEqual([]);
    expect(vm.proximoCritico).toBeNull();
  });
});

/**
 * Que "todavía no se sabe" no se muestre como "no cumple nada" (#125).
 *
 * **Medido en el seed antes de arreglarlo:** de las tres plantas de la empresa
 * 1, dos —Faena Antofagasta y Oficina Santiago— tienen **cero evaluaciones de
 * artículo**, y el tablero ejecutivo las mostraba en rojo con "0 % de
 * cumplimiento". Es la pantalla que el Admin Empresa mira para decidir dónde
 * poner recursos: lo mandaba a apagar un incendio que nadie había comprobado.
 *
 * La causa era `if total else 0.0` en `services/dashboard.py`, y un
 * `.get(f.id, {}).get('compliance_percentage', 0.0)` para las plantas que ni
 * siquiera aparecen en el agregado. `resumen_cumplimiento.py` ya devolvía
 * `None` en el mismo caso — dos servicios calculando el mismo número, uno bien
 * y otro no.
 *
 * **Ojo con el typecheck:** `apps/web` tiene `"strict": false`, así que
 * `number | null` pasa por `number` sin error y la aritmética sobre `null` no
 * se detecta al compilar. Estas pruebas son la única red para esto.
 */
describe('sin evaluar no es 0% en el tablero', () => {
  it('conserva el null de la API en vez de convertirlo en cero', () => {
    const vm = fromApiMetrics(
      apiResponse({ global: { ...apiResponse().global, compliance_percentage: null } }),
    );

    expect(vm.cumplimientoGlobal).toBeNull();
  });

  it('lo conserva también por planta', () => {
    const vm = fromApiMetrics(
      apiResponse({
        facilities: [
          {
            facility_id: 'f1',
            name: 'Faena Antofagasta',
            commune_code: '02101',
            region_code: 'II',
            compliance_percentage: null,
            non_compliant_count: 0,
            nc_open_count: 0,
            critical_deadline: null,
          },
        ],
      }),
    );

    expect(vm.plantas[0]!.cumplimientoPct).toBeNull();
  });

  it('un 0 de la API SÍ llega como 0, no como null', () => {
    // `null` y `0` viajan distinto y tienen que llegar distinto. Un `??` mal
    // puesto en el adaptador convertiría el cero medido en "sin evaluar", que
    // es el error opuesto y igual de grave: taparía un incumplimiento real.
    const vm = fromApiMetrics(
      apiResponse({ global: { ...apiResponse().global, compliance_percentage: 0 } }),
    );

    expect(vm.cumplimientoGlobal).toBe(0);
  });
});
