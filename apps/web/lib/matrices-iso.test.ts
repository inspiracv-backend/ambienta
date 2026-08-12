import { describe, it, expect } from 'vitest';
import {
  AspectoAmbientalSchema,
  RiesgoOportunidadSchema,
  EquipoReguladoSchema,
  LegalNormSchema,
  aspectoSinTratar,
  sinOperadorHabilitado,
  calcularPuntajeSignificancia,
  FEATURE_FLAGS,
} from '@ambienta/shared';
import { mockAspectosAmbientales, mockConfiguracionMatrices } from '@/mocks/aspectos-ambientales';
import { mockRiesgosOportunidades, mockEquiposRegulados } from '@/mocks/riesgos-oportunidades';
import { mockLegalNorms } from '@/mocks/catalog';

describe('feature flag matricesIso', () => {
  it('viene encendida por defecto', () => {
    expect(FEATURE_FLAGS.matricesIso).toBe(true);
  });
});

describe('AspectoAmbiental', () => {
  it('valida todos los mocks', () => {
    for (const aspecto of mockAspectosAmbientales) {
      expect(AspectoAmbientalSchema.safeParse(aspecto).success).toBe(true);
    }
  });

  it('cubre las tres condiciones de operacion que exige §6.1.2', () => {
    const condiciones = new Set(mockAspectosAmbientales.map((a) => a.condicionOperacion));
    expect(condiciones).toContain('normal');
    expect(condiciones).toContain('emergencia');
  });

  it('rechaza un aspecto sin actividad', () => {
    const invalido = { ...mockAspectosAmbientales[0], actividad: '' };
    expect(AspectoAmbientalSchema.safeParse(invalido).success).toBe(false);
  });

  it('detecta un aspecto significativo sin requisito ni riesgo asociado', () => {
    const caldera = mockAspectosAmbientales.find((a) => a.id === 'asp-2')!;
    expect(aspectoSinTratar(caldera)).toBe(true);

    const vertido = mockAspectosAmbientales.find((a) => a.id === 'asp-1')!;
    expect(aspectoSinTratar(vertido)).toBe(false);
  });

  it('no marca como pendiente un aspecto no significativo', () => {
    const papel = mockAspectosAmbientales.find((a) => a.id === 'asp-4')!;
    expect(aspectoSinTratar(papel)).toBe(false);
  });
});

describe('calculo de significancia', () => {
  const criterios = mockConfiguracionMatrices.criteriosSignificancia;

  it('multiplica los criterios con el metodo producto', () => {
    const valores = [
      { criterioId: 'crit-severidad', valor: 2 },
      { criterioId: 'crit-frecuencia', valor: 3 },
      { criterioId: 'crit-alcance', valor: 2 },
      { criterioId: 'crit-legal', valor: 3 },
    ];
    expect(calcularPuntajeSignificancia(valores, criterios, 'producto')).toBe(36);
  });

  it('suma cuando el metodo es suma', () => {
    const valores = [
      { criterioId: 'crit-severidad', valor: 2 },
      { criterioId: 'crit-frecuencia', valor: 3 },
    ];
    expect(calcularPuntajeSignificancia(valores, criterios, 'suma')).toBe(5);
  });

  it('devuelve cero sin criterios evaluados', () => {
    expect(calcularPuntajeSignificancia([], criterios, 'producto')).toBe(0);
  });

  it('el umbral separa significativos de no significativos', () => {
    const umbral = mockConfiguracionMatrices.umbralSignificancia;
    for (const aspecto of mockAspectosAmbientales) {
      if (!aspecto.evaluacion) continue;
      expect(aspecto.significativo).toBe(aspecto.evaluacion.puntaje >= umbral);
    }
  });
});

describe('RiesgoOportunidad', () => {
  it('valida todos los mocks', () => {
    for (const ryo of mockRiesgosOportunidades) {
      const result = RiesgoOportunidadSchema.safeParse(ryo);
      expect(result.success, `${ryo.codigo}: ${JSON.stringify(result)}`).toBe(true);
    }
  });

  it('exige justificacion al aceptar un riesgo', () => {
    const aceptado = mockRiesgosOportunidades.find((r) => r.tratamiento === 'aceptar')!;
    const sinJustificar = { ...aceptado, justificacionTratamiento: undefined };
    expect(RiesgoOportunidadSchema.safeParse(sinJustificar).success).toBe(false);
  });

  it('exige justificacion al descartar una oportunidad', () => {
    const base = mockRiesgosOportunidades.find((r) => r.tipo === 'oportunidad')!;
    const descartada = { ...base, tratamiento: 'descartar' as const };
    expect(RiesgoOportunidadSchema.safeParse(descartada).success).toBe(false);
  });

  it('no permite mitigar una oportunidad', () => {
    const base = mockRiesgosOportunidades.find((r) => r.tipo === 'oportunidad')!;
    const invalido = { ...base, tratamiento: 'mitigar' as const };
    expect(RiesgoOportunidadSchema.safeParse(invalido).success).toBe(false);
  });

  it('no permite aprovechar un riesgo', () => {
    const base = mockRiesgosOportunidades.find((r) => r.tipo === 'riesgo')!;
    const invalido = { ...base, tratamiento: 'aprovechar' as const };
    expect(RiesgoOportunidadSchema.safeParse(invalido).success).toBe(false);
  });

  it('admite origen en el cambio climatico, que agrega la edicion 2026', () => {
    const climatico = mockRiesgosOportunidades.find((r) => r.origen === 'cambio_climatico');
    expect(climatico).toBeDefined();
  });
});

describe('EquipoRegulado', () => {
  it('valida todos los mocks', () => {
    for (const equipo of mockEquiposRegulados) {
      expect(EquipoReguladoSchema.safeParse(equipo).success).toBe(true);
    }
  });

  it('detecta un equipo operativo sin operador habilitado', () => {
    const grupo = mockEquiposRegulados.find((e) => e.id === 'equipo-2')!;
    expect(sinOperadorHabilitado(grupo, '2026-07-30')).toBe(true);
  });

  it('considera habilitada una certificacion vigente', () => {
    const caldera = mockEquiposRegulados.find((e) => e.id === 'equipo-1')!;
    expect(sinOperadorHabilitado(caldera, '2026-07-30')).toBe(false);
  });

  it('deja de considerar habilitada una certificacion vencida', () => {
    const caldera = mockEquiposRegulados.find((e) => e.id === 'equipo-1')!;
    expect(sinOperadorHabilitado(caldera, '2026-10-01')).toBe(true);
  });

  it('no alerta sobre equipos dados de baja', () => {
    const dadoDeBaja = { ...mockEquiposRegulados[1], estado: 'baja' as const };
    expect(sinOperadorHabilitado(dadoDeBaja, '2026-07-30')).toBe(false);
  });
});

describe('compatibilidad de LegalNorm', () => {
  it('las normas existentes siguen validando sin los campos nuevos', () => {
    for (const norma of mockLegalNorms) {
      expect(LegalNormSchema.safeParse(norma).success).toBe(true);
    }
  });

  it('acepta los campos nuevos cuando estan presentes', () => {
    const ampliada = {
      ...mockLegalNorms[0],
      categoriaRequisito: 'legal' as const,
      subtipo: 'decreto' as const,
      organismoFiscalizador: 'SISS',
      vigencia: { estado: 'vigente' as const, desde: '1998-07-07' },
      aplicabilidad: {
        determinadaPor: 'manual' as const,
        actividadesEconomicas: ['1030'],
        criterio: 'Descarga de riles a cuerpo receptor superficial',
        aspectoAmbientalIds: ['asp-1'],
      },
      evaluacionPeriodica: { frecuenciaMeses: 12, ultimaEvaluacion: '2026-03-12' },
    };
    expect(LegalNormSchema.safeParse(ampliada).success).toBe(true);
  });

  it('acepta obligacion de monitoreo y evidencia fisica en un articulo', () => {
    const norma = structuredClone(mockLegalNorms[0]);
    norma.articulos[0] = {
      ...norma.articulos[0],
      obligacionMonitoreo: {
        parametros: [{ nombre: 'Cloro libre residual', unidad: 'mg/L', limiteMaximo: 0.5 }],
        frecuencia: 'mensual',
        requiereLaboratorioAcreditado: true,
        cuerpoReceptor: 'Estero Los Robles',
      },
      evidenciaFisica: {
        ubicacion: 'Archivo fisico, oficina de calidad, carpeta 12',
        custodioId: 'user-encargado',
      },
    };
    expect(LegalNormSchema.safeParse(norma).success).toBe(true);
  });
});
