import { describe, expect, it } from 'vitest';
import {
  COBERTURA_VACIA,
  mapearCobertura,
  porcentajeClasificado,
  urgenciaDe,
  type CoberturaDeSector,
} from './clasificacion-normativa';

/**
 * Lo que hay que proteger acá es que **el tablero no se vea mejor de lo que
 * está**. Esta pantalla existe porque `norm_sectors` está vacía y nadie se
 * entera: si el conteo se equivoca hacia el lado optimista, la pantalla que se
 * inventó para hacer visible el trabajo pendiente lo esconde otra vez.
 */

function sector(parcial: Partial<CoberturaDeSector>): CoberturaDeSector {
  return {
    sectorId: 1,
    codigo: 'C',
    nombre: 'Industria manufacturera',
    directas: 0,
    recomendadas: 0,
    total: 0,
    ...parcial,
  };
}

describe('urgencia por sector', () => {
  it('un sector en cero es el peor caso, no el mejor', () => {
    // Es fácil leerlo al revés: "no hay nada rojo, vamos bien". Un sector sin
    // normativa significa que una empresa de ese rubro entra, completa su
    // perfil y no recibe ninguna obligación.
    expect(urgenciaDe(sector({}))).toBe('sin-normativa');
  });

  it('solo recomendadas no es lo mismo que tener obligatorias', () => {
    // `indirecta` y `referencial` se proponen; no obligan. Un sector así deja
    // a la empresa decidiendo qué cumplir, que no es lo que la ley hace.
    expect(urgenciaDe(sector({ recomendadas: 4, total: 4 }))).toBe('solo-recomendadas');
  });

  it('con al menos una obligatoria el sector está cubierto', () => {
    expect(urgenciaDe(sector({ directas: 1, total: 1 }))).toBe('con-obligatorias');
  });
});

describe('porcentaje clasificado', () => {
  it('sin normas en el catálogo es null, no cero', () => {
    // Cero diría "nadie ha clasificado nada". `null` dice "todavía no hay nada
    // que clasificar". Son cosas distintas y la pantalla las muestra distinto.
    expect(porcentajeClasificado(COBERTURA_VACIA)).toBeNull();
  });

  it('cuenta las clasificadas, no las pendientes', () => {
    expect(
      porcentajeClasificado({ ...COBERTURA_VACIA, normasTotales: 10, normasSinClasificar: 3 }),
    ).toBe(70);
  });

  it('nada clasificado da 0, que sí es un cero real', () => {
    expect(
      porcentajeClasificado({ ...COBERTURA_VACIA, normasTotales: 12, normasSinClasificar: 12 }),
    ).toBe(0);
  });
});

describe('mapeo de la respuesta', () => {
  it('lee la forma que devuelve la API', () => {
    const c = mapearCobertura({
      normas_totales: 12,
      normas_sin_clasificar: 12,
      sectores_sin_normativa: 21,
      por_sector: [
        { sector_id: 3, codigo: 'C', nombre: 'Industria manufacturera', directas: 0, recomendadas: 0, total: 0 },
      ],
    });

    expect(c.normasTotales).toBe(12);
    expect(c.sectoresSinNormativa).toBe(21);
    expect(c.porSector[0]).toEqual({
      sectorId: 3,
      codigo: 'C',
      nombre: 'Industria manufacturera',
      directas: 0,
      recomendadas: 0,
      total: 0,
    });
  });

  it('una respuesta rota no inventa cobertura', () => {
    // El riesgo acá es al revés de lo habitual: rellenar con valores por
    // defecto optimistas mostraría un tablero limpio cuando en realidad no se
    // pudo leer nada.
    expect(mapearCobertura(null)).toEqual(COBERTURA_VACIA);
    expect(mapearCobertura({}).porSector).toEqual([]);
    expect(mapearCobertura({ por_sector: 'no es una lista' }).porSector).toEqual([]);
  });
});
