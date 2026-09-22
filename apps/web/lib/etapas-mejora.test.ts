import { describe, expect, it } from 'vitest';
import { cicloDesdeApi, cuerpoDe, etapasCambiadas, type EtapaApi } from './etapas-mejora';

function fila(kind: EtapaApi['kind'], over: Partial<EtapaApi> = {}): EtapaApi {
  return {
    id: `id-${kind}`,
    kind,
    responsable_user_id: null,
    metodologia_id: null,
    fecha_ejecucion: null,
    due_date: null,
    completada_en: null,
    eficaz: null,
    causa_se_repitio: null,
    cumplio_proposito: null,
    requiere_actualizar_riesgos: null,
    requiere_cambios_sgc: null,
    observaciones: null,
    evidencia_urls: [],
    datos: {},
    ...over,
  };
}

const CICLO_COMPLETO = [
  fila('registro', { fecha_ejecucion: '2026-09-01', completada_en: '2026-09-01T12:00:00Z' }),
  fila('correccion'),
  fila('analisis_causa'),
  fila('accion_correctiva'),
  fila('seguimiento'),
];

describe('el tri-estado del seguimiento', () => {
  it('"sin verificar" viaja como null y no como false', () => {
    const ciclo = cicloDesdeApi(CICLO_COMPLETO);
    const cuerpo = cuerpoDe('seguimiento', ciclo)!;
    // Si `null` se volviera `false`, "¿la causa se repitió?" quedaría en NO —
    // la respuesta favorable— sin que nadie la contestara.
    expect(cuerpo.eficaz).toBeNull();
    expect(cuerpo.causa_se_repitio).toBeNull();
    expect(cuerpo.requiere_cambios_sgc).toBeNull();
    expect((cuerpo.datos as Record<string, unknown>).requiereActualizarFoda).toBeNull();
  });

  it('un NO explícito se conserva como false', () => {
    const ciclo = cicloDesdeApi([fila('seguimiento', { eficaz: false })]);
    expect(cuerpoDe('seguimiento', ciclo)!.eficaz).toBe(false);
  });
});

describe('los vacíos', () => {
  it('se mandan como null: un UUID o una fecha vacíos responden 422', () => {
    const ciclo = cicloDesdeApi(CICLO_COMPLETO);
    ciclo.analisisCausa = { ...ciclo.analisisCausa!, metodologiaId: '', responsableEtapaId: '', fechaEjecucion: '' };
    const cuerpo = cuerpoDe('analisis_causa', ciclo)!;
    expect(cuerpo.metodologia_id).toBeNull();
    expect(cuerpo.responsable_user_id).toBeNull();
    expect(cuerpo.fecha_ejecucion).toBeNull();
  });
});

describe('la fecha que completa cada etapa', () => {
  it('en la acción correctiva es la de finalización', () => {
    const ciclo = cicloDesdeApi(CICLO_COMPLETO);
    ciclo.accionCorrectiva = { ...ciclo.accionCorrectiva!, fechaInicial: '2026-09-02', fechaFinalizacion: '2026-09-10' };
    expect(cuerpoDe('accion_correctiva', ciclo)!.fecha_ejecucion).toBe('2026-09-10');
  });

  it('en el seguimiento es la de seguimiento', () => {
    const ciclo = cicloDesdeApi(CICLO_COMPLETO);
    ciclo.seguimiento = { ...ciclo.seguimiento!, fechaSeguimiento: '2026-09-12' };
    expect(cuerpoDe('seguimiento', ciclo)!.fecha_ejecucion).toBe('2026-09-12');
  });
});

describe('qué se manda al guardar', () => {
  it('sin tocar nada no se manda ninguna etapa', () => {
    expect(etapasCambiadas(CICLO_COMPLETO, cicloDesdeApi(CICLO_COMPLETO))).toEqual([]);
  });

  it('solo la etapa que cambió', () => {
    const ciclo = cicloDesdeApi(CICLO_COMPLETO);
    ciclo.correccion = { ...ciclo.correccion!, correccionInmediata: 'Se aisló el derrame' };
    const cambios = etapasCambiadas(CICLO_COMPLETO, ciclo);
    expect(cambios.map((c) => c.etapa.kind)).toEqual(['correccion']);
  });

  it('el registro nunca: se cumple al registrar', () => {
    expect(cuerpoDe('registro', cicloDesdeApi(CICLO_COMPLETO))).toBeNull();
  });

  it('lo guardado vuelve igual: ida y vuelta sin cambios espurios', () => {
    const guardado = [
      fila('analisis_causa', {
        metodologia_id: 'm-1',
        fecha_ejecucion: '2026-09-05',
        datos: { cincoPorques: ['a', 'b', '', '', ''], espinaPescado: null, causaRaiz: 'mantención' },
      }),
      fila('seguimiento', {
        eficaz: true,
        datos: { requiereActualizarFoda: false, salidas: [] },
        observaciones: 'ok',
      }),
    ];
    expect(etapasCambiadas(guardado, cicloDesdeApi(guardado))).toEqual([]);
  });
});

describe('la fecha límite', () => {
  it('viaja en el cuerpo, y vacía como null', () => {
    const ciclo = cicloDesdeApi([fila('correccion', { due_date: '2026-09-20' })]);
    expect(cuerpoDe('correccion', ciclo)!.due_date).toBe('2026-09-20');
    ciclo.limites = { correccion: '' };
    expect(cuerpoDe('correccion', ciclo)!.due_date).toBeNull();
  });

  it('cambiarla cuenta como cambio de la etapa', () => {
    const filas = [fila('correccion'), fila('seguimiento')];
    const ciclo = cicloDesdeApi(filas);
    ciclo.limites = { ...ciclo.limites, seguimiento: '2026-10-01' };
    expect(etapasCambiadas(filas, ciclo).map((c) => c.etapa.kind)).toEqual(['seguimiento']);
  });
});

describe('qué etapas hay', () => {
  it('las decide la base: un riesgo nace sin corrección ni análisis', () => {
    const ciclo = cicloDesdeApi([fila('registro'), fila('accion_correctiva'), fila('seguimiento')]);
    expect(ciclo.correccion).toBeUndefined();
    expect(ciclo.analisisCausa).toBeUndefined();
    expect(ciclo.accionCorrectiva).toBeDefined();
  });
});
