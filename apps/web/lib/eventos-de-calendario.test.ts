import { describe, expect, it } from 'vitest';
import { claveDeDia, eventosDeEquipos, eventosDeRevisiones } from './eventos-de-calendario';

/** Lo que vence y no es una tarea: revisiones de normas e inscripciones de equipos. */

describe('las revisiones de normas', () => {
  const fila = (over: Record<string, unknown>) => ({
    matrix_norm_id: 'mn1',
    titulo: 'DS 90',
    proxima_revision: null,
    motivo_sin_fecha: null,
    vencida: false,
    ...over,
  });

  it('con fecha van al calendario, con la fecha tal cual', () => {
    const { eventos, sinFecha } = eventosDeRevisiones([fila({ proxima_revision: '2026-12-02', vencida: false })]);

    expect(eventos).toEqual([
      expect.objectContaining({ fecha: '2026-12-02', tipo: 'revision_norma', titulo: 'DS 90', href: '/matriz-legal' }),
    ]);
    expect(sinFecha).toEqual([]);
  });

  it('sin fecha no se pierden: van a la lista, con el motivo en palabras', () => {
    const { eventos, sinFecha } = eventosDeRevisiones([
      fila({ matrix_norm_id: 'a', motivo_sin_fecha: 'nunca_evaluada' }),
      fila({ matrix_norm_id: 'b', motivo_sin_fecha: 'evaluada_sin_fecha' }),
      fila({ matrix_norm_id: 'c', motivo_sin_fecha: 'por_evento' }),
    ]);

    expect(eventos).toEqual([]);
    expect(sinFecha.map((s) => s.motivo)).toEqual([
      'Nunca se evaluó: no hay desde dónde contar.',
      'Se evaluó, pero sin fecha registrada.',
      'Se revisa por evento, no periódicamente.',
    ]);
  });
});

describe('las inscripciones de equipos', () => {
  it('sin fecha no entran, y las pasadas salen vencidas', () => {
    const eventos = eventosDeEquipos(
      [
        { id: 'e1', name: 'Caldera 1', registration_expires_at: '2026-09-01' },
        { id: 'e2', name: 'Grupo electrógeno', registration_expires_at: '2026-10-15' },
        { id: 'e3', name: 'Sin inscripción', registration_expires_at: null },
      ],
      '2026-09-21',
    );

    expect(eventos.map((e) => [e.titulo, e.vencido])).toEqual([
      ['Caldera 1', true],
      ['Grupo electrógeno', false],
    ]);
  });
});

describe('el dia de una celda', () => {
  it('es el dia local, sin pasar por UTC', () => {
    // `toISOString()` daria el dia en UTC: a las 22:00 de Chile ya es mañana.
    expect(claveDeDia(new Date(2026, 8, 2, 22, 30))).toBe('2026-09-02');
    expect(claveDeDia(new Date(2026, 0, 5))).toBe('2026-01-05');
  });
});
