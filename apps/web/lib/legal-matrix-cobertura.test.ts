import { describe, it, expect } from 'vitest';
import type { LegalNorm } from '@ambienta/shared';
import {
  computeNormCompliance,
  computeNormCoverage,
  countArticulosSinEvaluar,
} from '@/lib/legal-matrix';

function norma(respuestas: LegalNorm['articulos'][number]['respuesta'][]): LegalNorm {
  return {
    id: 'n1',
    tenantId: 't1',
    plantIds: [],
    tipoDocumento: 'Decreto',
    nombre: 'Norma de prueba',
    fuente: 'BCN',
    articulos: respuestas.map((respuesta, i) => ({
      id: `a${i}`,
      normId: 'n1',
      numero: `${i + 1}`,
      descripcion: '',
      respuesta,
      incluidoEnCalculo: true,
    })),
  };
}

describe('cumplimiento vs cobertura', () => {
  it('el caso que motiva separar los dos indicadores', () => {
    // Un artículo cumplido y cuatro sin evaluar.
    const n = norma(['SI', 'N_E', 'N_E', 'N_E', 'N_E']);

    // Cumplimiento dice 100%: es cierto sobre lo evaluado.
    expect(computeNormCompliance(n)).toBe(1);
    // Cobertura dice 20%: es lo que faltaba saber.
    expect(computeNormCoverage(n)).toBeCloseTo(0.2);
    expect(countArticulosSinEvaluar(n)).toBe(4);
  });

  it('una norma completamente evaluada tiene cobertura total', () => {
    const n = norma(['SI', 'NO', 'SI']);
    expect(computeNormCoverage(n)).toBe(1);
    expect(countArticulosSinEvaluar(n)).toBe(0);
  });

  it('los no aplicables salen del denominador de cobertura', () => {
    const n = norma(['SI', 'NA', 'NA']);
    // Un solo artículo aplicable, y está evaluado.
    expect(computeNormCoverage(n)).toBe(1);
  });

  it('un no aplicable no se confunde con un sin evaluar', () => {
    const conNa = norma(['SI', 'NA']);
    const conNe = norma(['SI', 'N_E']);
    expect(computeNormCoverage(conNa)).toBe(1);
    expect(computeNormCoverage(conNe)).toBeCloseTo(0.5);
  });

  it('una norma sin artículos aplicables no reporta cobertura cero', () => {
    // Cero de cero es 100% revisado, no 0% — no hay nada que revisar.
    expect(computeNormCoverage(norma(['NA', 'NA']))).toBe(1);
  });

  it('excluir del cálculo de cumplimiento no esconde el artículo de la cobertura', () => {
    const n = norma(['SI', 'N_E']);
    n.articulos[1].incluidoEnCalculo = false;
    expect(computeNormCompliance(n)).toBe(1);
    // Sigue contando como no revisado: excluirlo del cálculo es una decisión,
    // taparlo en la cobertura sería otra cosa.
    expect(computeNormCoverage(n)).toBeCloseTo(0.5);
  });
});
