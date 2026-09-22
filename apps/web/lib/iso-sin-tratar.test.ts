import { describe, expect, it } from 'vitest';
import { aspectoSinTratar, type AspectoApi, type RiesgoApi } from './iso-store';

const aspecto = (extra: Partial<AspectoApi> = {}) =>
  ({ id: 'asp-1', significancia: 'significant', articleComplianceId: null, ...extra }) as AspectoApi;
const riesgo = (aspectoAmbientalId: string | null) => ({ id: 'r-1', aspectoAmbientalId }) as RiesgoApi;

describe('un aspecto significativo sin tratar', () => {
  it('lo es si ningun riesgo u oportunidad lo trata', () => {
    expect(aspectoSinTratar(aspecto(), [riesgo(null)])).toBe(true);
  });

  it('el requisito legal que le aplica no es un tratamiento', () => {
    // Hasta el 21-sep esta copia lo contaba como tratado y el panel del servidor
    // no: la tabla y el panel decian cosas distintas del mismo aspecto.
    expect(aspectoSinTratar(aspecto({ articleComplianceId: 'ac-1' }), [])).toBe(true);
  });

  it('con un riesgo enlazado esta tratado', () => {
    expect(aspectoSinTratar(aspecto(), [riesgo('asp-1')])).toBe(false);
  });

  it('uno no significativo nunca esta "sin tratar"', () => {
    expect(aspectoSinTratar(aspecto({ significancia: 'not_significant' }), [])).toBe(false);
  });
});
