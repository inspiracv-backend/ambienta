import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  TRANSICIONES,
  cuerpoDeAuditoria,
  cuerpoDePregunta,
  cuerpoDeRespuesta,
  mediodiaLocal,
  sugerirCodigo,
  type EstadoAuditoria,
} from './ciclo-de-auditoria';

/**
 * Lo que sale a la API. `apps/api/tests/test_ciclo_de_auditoria.py` manda estos
 * mismos cuerpos: si cambia uno de los dos lados, falla uno de los dos.
 */
describe('los cuerpos que se mandan', () => {
  it('crear: los ocho campos de AuditCreate, con null y no vacío', () => {
    expect(
      cuerpoDeAuditoria({
        codigo: ' AUD-2026-004 ',
        titulo: 'Auditoría interna de residuos',
        tipo: 'internal',
        alcance: 'Gestión de residuos peligrosos',
        plantaId: null,
        inicio: '2026-09-22',
        fin: '',
        auditorLiderId: null,
      }),
    ).toEqual({
      code: 'AUD-2026-004',
      title: 'Auditoría interna de residuos',
      audit_type: 'internal',
      scope: 'Gestión de residuos peligrosos',
      facility_id: null,
      planned_start: mediodiaLocal('2026-09-22'),
      planned_end: null,
      lead_auditor_user_id: null,
    });
  });

  it('una pregunta nace sin `result`: responderla es otro paso', () => {
    expect(cuerpoDePregunta('  ¿Hay registro SIDREP? ', '')).toEqual({
      question: '¿Hay registro SIDREP?',
      process_id: null,
    });
  });

  it('responder no manda `assessed_at`: la fecha la pone el servidor', () => {
    expect(cuerpoDeRespuesta('nonconform', ' Dos manifiestos sin firma ')).toEqual({
      result: 'nonconform',
      notes: 'Dos manifiestos sin firma',
    });
    expect(cuerpoDeRespuesta('conform', '   ')).toEqual({ result: 'conform', notes: null });
  });
});

describe('la fecha planificada', () => {
  it('cae el mismo día del calendario que se eligió', () => {
    // Mandar `2026-09-22` a secas es medianoche UTC: en Chile, el 21.
    const instante = new Date(mediodiaLocal('2026-09-22'));
    expect(instante.getFullYear()).toBe(2026);
    expect(instante.getMonth()).toBe(8);
    expect(instante.getDate()).toBe(22);
  });
});

describe('el código sugerido', () => {
  it('sigue al mayor del año, no a la cantidad', () => {
    expect(sugerirCodigo(['AUD-2026-001', 'AUD-2026-007', 'AUD-2025-099', 'OTRO'], 2026)).toBe('AUD-2026-008');
  });
  it('arranca en 001', () => {
    expect(sugerirCodigo([], 2026)).toBe('AUD-2026-001');
  });
});

describe('las transiciones', () => {
  it('son las mismas que acepta la API', () => {
    // Un botón que la API rechaza se lee como un fallo del sistema.
    const py = readFileSync(resolve(__dirname, '../../api/app/services/audits.py'), 'utf-8');
    const bloque = py.split('AUDIT_STATUS_TRANSITIONS = {')[1]!.split('}')[0]!;
    const enLaApi: Record<string, string[]> = {};
    for (const [, desde, hacia] of Array.from(bloque.matchAll(/"(\w+)":\s*\[([^\]]*)\]/g))) {
      enLaApi[desde!] = Array.from(hacia!.matchAll(/"(\w+)"/g)).map((m) => m[1]!).sort();
    }
    const enLaPantalla = Object.fromEntries(
      (Object.keys(TRANSICIONES) as EstadoAuditoria[]).map((e) => [e, TRANSICIONES[e].map((t) => t.a).sort()]),
    );
    expect(enLaPantalla).toEqual(enLaApi);
  });
});
