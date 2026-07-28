import { describe, expect, it } from 'vitest';
import type { AuditLogEntry } from '@ambienta/shared';
import {
  actoresDe,
  exportarAuditoriaCsv,
  filtrarAuditoria,
  FILTROS_INICIALES,
  type FiltrosAuditoria,
} from './audit-log-filters';

/**
 * El audit log es un requisito legal (RNF-08, RNF-25) y su salida puede
 * terminar frente a un fiscalizador de la SMA. Dos cosas se prueban con
 * especial dureza: que un tenant jamás vea actividad de otro —una fuga aquí
 * expone qué hace la competencia— y que el CSV exportado no se corra de
 * columnas, porque un reporte mal formado es peor que no tenerlo.
 */

function evento(over: Partial<AuditLogEntry> & { id: string }): AuditLogEntry {
  return {
    tenantId: 'tenant-1',
    entidadTipo: 'obligacion',
    entidadId: 'obl-1',
    entidadLabel: 'DAE 2026',
    accion: 'actualizado',
    resumen: 'Actualizó la obligación',
    cambios: [],
    actorId: 'user-1',
    actorNombre: 'Camila Rojas',
    actorRol: 'usuario_interno',
    fecha: '2026-07-15T12:00:00.000Z',
    ...over,
  } as AuditLogEntry;
}

const f = (over: Partial<FiltrosAuditoria> = {}): FiltrosAuditoria => ({ ...FILTROS_INICIALES, ...over });

describe('aislamiento por tenant', () => {
  const entries = [
    evento({ id: 'propio', tenantId: 'tenant-1' }),
    evento({ id: 'ajeno', tenantId: 'tenant-2' }),
    evento({ id: 'plataforma', tenantId: null }),
  ];

  it('un tenant solo ve sus propios eventos', () => {
    expect(filtrarAuditoria(entries, 'tenant-1', f()).map((e) => e.id)).toEqual(['propio']);
  });

  it('no ve los eventos de plataforma', () => {
    // Que el Superadmin haya cambiado su límite de usuarios es actividad de
    // plataforma; mezclarla con su historial confundiría a quien lo audita.
    expect(filtrarAuditoria(entries, 'tenant-1', f()).map((e) => e.id)).not.toContain('plataforma');
  });

  it('el Superadmin ve solo la actividad de plataforma, no la de los tenants', () => {
    // CLAUDE.md: "Admin Global NO puede editar contenido de tenants". Tampoco
    // debe leer su operación diaria desde esta vista.
    expect(filtrarAuditoria(entries, null, f()).map((e) => e.id)).toEqual(['plataforma']);
  });

  it('el aislamiento se aplica aunque se busque por texto', () => {
    const conBusqueda = filtrarAuditoria(
      [evento({ id: 'ajeno', tenantId: 'tenant-2', resumen: 'Actualizó algo importante' })],
      'tenant-1',
      f({ texto: 'importante' }),
    );
    expect(conBusqueda).toHaveLength(0);
  });
});

describe('filtros', () => {
  const entries = [
    evento({ id: 'a', entidadTipo: 'obligacion', actorId: 'user-1', fecha: '2026-07-01T10:00:00.000Z' }),
    evento({ id: 'b', entidadTipo: 'no_conformidad', actorId: 'user-2', fecha: '2026-07-15T10:00:00.000Z' }),
    evento({ id: 'c', entidadTipo: 'obligacion', actorId: 'user-2', fecha: '2026-07-30T18:00:00.000Z' }),
  ];

  it('filtra por tipo de entidad', () => {
    expect(filtrarAuditoria(entries, 'tenant-1', f({ entidadTipo: 'obligacion' })).map((e) => e.id)).toEqual(['c', 'a']);
  });

  it('filtra por persona', () => {
    expect(filtrarAuditoria(entries, 'tenant-1', f({ actorId: 'user-2' })).map((e) => e.id)).toEqual(['c', 'b']);
  });

  it('incluye el día "hasta" completo', () => {
    // El evento 'c' ocurre a las 18:00 del día 30: filtrar "hasta el 30" debe
    // incluirlo, no cortar a su medianoche.
    const r = filtrarAuditoria(entries, 'tenant-1', f({ desde: '2026-07-01', hasta: '2026-07-30' }));
    expect(r.map((e) => e.id)).toContain('c');
  });

  it('excluye lo anterior a "desde"', () => {
    const r = filtrarAuditoria(entries, 'tenant-1', f({ desde: '2026-07-10' }));
    expect(r.map((e) => e.id)).not.toContain('a');
  });

  it('busca en resumen, entidad, actor y motivo', () => {
    const conMotivo = [
      evento({ id: 'x', motivo: 'La balanza no estaba calibrada' }),
      evento({ id: 'y', entidadLabel: 'SIDREP Q3' }),
      evento({ id: 'z', actorNombre: 'Diego Muñoz' }),
    ];
    expect(filtrarAuditoria(conMotivo, 'tenant-1', f({ texto: 'balanza' })).map((e) => e.id)).toEqual(['x']);
    expect(filtrarAuditoria(conMotivo, 'tenant-1', f({ texto: 'sidrep' })).map((e) => e.id)).toEqual(['y']);
    expect(filtrarAuditoria(conMotivo, 'tenant-1', f({ texto: 'diego' })).map((e) => e.id)).toEqual(['z']);
  });

  it('combina varios filtros', () => {
    const r = filtrarAuditoria(entries, 'tenant-1', f({ entidadTipo: 'obligacion', actorId: 'user-2' }));
    expect(r.map((e) => e.id)).toEqual(['c']);
  });

  it('ordena del más reciente al más antiguo', () => {
    expect(filtrarAuditoria(entries, 'tenant-1', f()).map((e) => e.id)).toEqual(['c', 'b', 'a']);
  });
});

describe('actoresDe', () => {
  it('devuelve cada actor una sola vez, ordenado por nombre', () => {
    const r = actoresDe([
      evento({ id: '1', actorId: 'u2', actorNombre: 'Zoe' }),
      evento({ id: '2', actorId: 'u1', actorNombre: 'Ana' }),
      evento({ id: '3', actorId: 'u1', actorNombre: 'Ana' }),
    ]);
    expect(r).toEqual([
      { id: 'u1', nombre: 'Ana' },
      { id: 'u2', nombre: 'Zoe' },
    ]);
  });
});

describe('exportarAuditoriaCsv', () => {
  it('incluye encabezado y una fila por evento', () => {
    const csv = exportarAuditoriaCsv([evento({ id: 'a' }), evento({ id: 'b' })]);
    expect(csv.split('\n')).toHaveLength(3);
  });

  it('aplana los cambios a texto legible en vez de JSON', () => {
    // El destinatario del archivo es un auditor con Excel, no un sistema.
    const csv = exportarAuditoriaCsv([
      evento({ id: 'a', cambios: [{ campo: 'Estado', antes: 'Abierto', despues: 'Cerrado' }] }),
    ]);
    expect(csv).toContain('Estado: Abierto → Cerrado');
  });

  it('entrecomilla los valores con coma para no correr las columnas', () => {
    const csv = exportarAuditoriaCsv([evento({ id: 'a', motivo: 'Se corrigió la fecha, estaba mal' })]);
    expect(csv).toContain('"Se corrigió la fecha, estaba mal"');
  });

  it('duplica las comillas internas', () => {
    const csv = exportarAuditoriaCsv([evento({ id: 'a', entidadLabel: 'Sector "A"' })]);
    expect(csv).toContain('"Sector ""A"""');
  });

  it('deja vacías las celdas de motivo y aprobación cuando no aplican', () => {
    const csv = exportarAuditoriaCsv([evento({ id: 'a' })]);
    expect(csv.split('\n')[1]!.endsWith(',,')).toBe(true);
  });

  it('incluye quién aprobó cuando el evento lo tiene (RF-32)', () => {
    const csv = exportarAuditoriaCsv([evento({ id: 'a', aprobadoPorNombre: 'Marcelo Fuentes' })]);
    expect(csv).toContain('Marcelo Fuentes');
  });
});
