import { describe, expect, it } from 'vitest';
import type { AspectoAmbiental, LegalNorm } from '@ambienta/shared';
import { calcularCompletitudCadena } from './completitud-cadena';

function aspecto(over: Partial<AspectoAmbiental> = {}): AspectoAmbiental {
  return {
    id: 'asp-1',
    tenantId: 't-1',
    procesoId: 'proc-1',
    actividad: 'Chancado',
    aspecto: 'Emision de material particulado',
    impacto: 'Deterioro de la calidad del aire',
    tipoAspecto: 'emision',
    condicionOperacion: 'normal',
    etapaCicloVida: 'operacion',
    plantId: 'planta-1',
    fechaIdentificacion: '2026-01-15',
    significativo: false,
    requisitoLegalIds: [],
    riesgoOportunidadIds: [],
    ...over,
  } as AspectoAmbiental;
}

/** `aspectoAmbientalIds` vive dentro de `aplicabilidad`, que es opcional. */
function justificadaPor(...aspectoAmbientalIds: string[]) {
  return {
    aplicabilidad: {
      determinadaPor: 'manual' as const,
      actividadesEconomicas: [],
      aspectoAmbientalIds,
    },
  };
}

function norma(over: Partial<LegalNorm> = {}): LegalNorm {
  return {
    id: 'norm-1',
    tenantId: 't-1',
    plantIds: [],
    tipoDocumento: 'Decreto',
    nombre: 'D.S. 138',
    fuente: 'RCA',
    articulos: [],
    ...justificadaPor(),
    ...over,
  } as LegalNorm;
}

describe('completitud de la cadena', () => {
  it('el caso que motiva el indicador: todo cumplido y nada justificado', () => {
    // Tres requisitos evaluados al 100%, pero ningun aspecto los derivo.
    // Cumplimiento y cobertura se ven perfectos; la cadena esta vacia.
    const r = calcularCompletitudCadena(
      [],
      [norma({ id: 'n-1' }), norma({ id: 'n-2' }), norma({ id: 'n-3' })],
    );

    expect(r.requisitos).toBe(3);
    expect(r.requisitosSinAspecto).toBe(3);
    expect(r.completitud).toBe(0);
  });

  it('un aspecto no significativo sin tratar no cuenta como hueco', () => {
    // Decidir que algo no es significativo ES la decision de no tratarlo.
    const r = calcularCompletitudCadena([aspecto({ significativo: false })], []);

    expect(r.aspectosSignificativos).toBe(0);
    expect(r.aspectosSinTratar).toBe(0);
    expect(r.completitud).toBe(1);
  });

  it('un aspecto significativo sin requisito ni riesgo es un hueco', () => {
    const r = calcularCompletitudCadena([aspecto({ significativo: true })], []);

    expect(r.aspectosSignificativos).toBe(1);
    expect(r.aspectosSinTratar).toBe(1);
    expect(r.completitud).toBe(0);
  });

  it('basta un riesgo para considerar tratado un aspecto significativo', () => {
    // No hace falta requisito legal: tratar por riesgo tambien es tratar.
    const r = calcularCompletitudCadena(
      [aspecto({ significativo: true, riesgoOportunidadIds: ['r-1'] })],
      [],
    );

    expect(r.aspectosSinTratar).toBe(0);
    expect(r.completitud).toBe(1);
  });

  it('la cadena completa da 1', () => {
    const r = calcularCompletitudCadena(
      [aspecto({ id: 'a-1', significativo: true, requisitoLegalIds: ['n-1'] })],
      [norma({ id: 'n-1', ...justificadaPor('a-1') })],
    );

    expect(r.completitud).toBe(1);
    expect(r.enlacesRotos).toBe(0);
  });

  it('promedia los dos lados de la cadena', () => {
    // 1 aspecto significativo tratado + 1 requisito sin justificar = 1 de 2.
    const r = calcularCompletitudCadena(
      [aspecto({ id: 'a-1', significativo: true, requisitoLegalIds: ['n-1'] })],
      [norma({ id: 'n-1', ...justificadaPor() })],
    );

    expect(r.completitud).toBe(0.5);
  });

  it('sin aspectos ni requisitos no reporta cero', () => {
    // Misma convencion que computeNormCoverage: la ausencia de datos no es un
    // incumplimiento. Reportar 0 pintaria de rojo a una empresa recien creada.
    expect(calcularCompletitudCadena([], []).completitud).toBe(1);
  });

  it('cuenta los enlaces que apuntan a algo que no existe', () => {
    const r = calcularCompletitudCadena(
      [aspecto({ id: 'a-1', significativo: true, requisitoLegalIds: ['n-borrada'] })],
      [norma({ id: 'n-1', ...justificadaPor('a-borrado') })],
    );

    expect(r.enlacesRotos).toBe(2);
  });

  it('un enlace roto no infla la completitud', () => {
    // El aspecto apunta a una norma que no existe. Para `aspectoSinTratar` ya
    // no esta "sin tratar" —tiene un id puesto— asi que la razon lo cuenta como
    // resuelto. Por eso los enlaces rotos se reportan aparte: si se mezclaran,
    // un id podrido se leeria igual que un enlace correcto.
    const r = calcularCompletitudCadena(
      [aspecto({ id: 'a-1', significativo: true, requisitoLegalIds: ['n-borrada'] })],
      [],
    );

    expect(r.enlacesRotos).toBe(1);
    expect(r.aspectosSinTratar).toBe(0);
  });

  it('los enlaces rotos no entran en la razon', () => {
    const sano = calcularCompletitudCadena(
      [aspecto({ id: 'a-1', significativo: true, requisitoLegalIds: ['n-1'] })],
      [norma({ id: 'n-1', ...justificadaPor('a-1') })],
    );
    const roto = calcularCompletitudCadena(
      [aspecto({ id: 'a-1', significativo: true, requisitoLegalIds: ['n-1'] })],
      [norma({ id: 'n-1', ...justificadaPor('a-inexistente') })],
    );

    expect(sano.completitud).toBe(roto.completitud);
    expect(roto.enlacesRotos).toBeGreaterThan(sano.enlacesRotos);
  });
});
