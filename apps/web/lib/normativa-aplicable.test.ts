import { describe, expect, it } from 'vitest';
import {
  esObligatoria,
  EXPLICACION_DEL_ESTADO,
  mapearDesactualizada,
  mapearNormativa,
  matrizMasReciente,
  NORMATIVA_VACIA,
} from './normativa-aplicable';

/**
 * El riesgo de esta pantalla es puntual y grave: **que una lista vacía se lea
 * como "esta empresa está en regla"**.
 *
 * Vacía tiene tres causas. Dos de ellas —falta el sector, nadie clasificó el
 * sector— significan que todavía no se sabe qué obligaciones tiene, no que no
 * tenga. Si el mapeo o el mensaje colapsan esos casos en uno solo, la pantalla
 * le dice a una empresa que no debe nada cuando en realidad nadie miró.
 */

describe('el estado que explica una lista vacía', () => {
  it('cada estado vacío dice algo distinto, porque la acción es distinta', () => {
    // En un caso la acción es de la empresa; en el otro, nuestra. Un mensaje
    // genérico dejaría a las dos partes esperando a la otra.
    const sinPerfil = EXPLICACION_DEL_ESTADO.sin_perfil;
    const sinClasificar = EXPLICACION_DEL_ESTADO.sector_sin_clasificar;

    expect(sinPerfil).not.toBeNull();
    expect(sinClasificar).not.toBeNull();
    expect(sinPerfil!.titulo).not.toBe(sinClasificar!.titulo);
  });

  it('«sector sin clasificar» dice explícitamente que no significa estar en regla', () => {
    // Es el caso peligroso: sin esta frase, la pantalla muestra cero normas y
    // la empresa concluye lo contrario de lo que pasa.
    expect(EXPLICACION_DEL_ESTADO.sector_sin_clasificar!.detalle).toMatch(
      /no significa que la empresa no tenga obligaciones/i,
    );
  });

  it('con normativa no hay explicación que mostrar', () => {
    expect(EXPLICACION_DEL_ESTADO.con_normativa).toBeNull();
  });
});

describe('mapeo de la normativa aplicable', () => {
  it('lee la forma que devuelve la API, con el motivo de cada norma', () => {
    const r = mapearNormativa({
      estado: 'con_normativa',
      sector_id: 3,
      total: 1,
      obligatorias: [
        {
          norm_id: 'n1',
          title: 'DS 594',
          norm_type: 'decreto',
          norm_number: '594',
          sector_id: 3,
          applicability_level: 'directa',
          rationale: 'Aplica a toda instalación con trabajadores',
        },
      ],
      recomendadas: [],
    });

    expect(r.estado).toBe('con_normativa');
    expect(r.obligatorias).toHaveLength(1);
    // El motivo es la respuesta a "cómo determinaron que esto les aplica".
    // Perderlo en el mapeo deja una lista que hay que defender de memoria.
    expect(r.obligatorias[0].motivo).toBe('Aplica a toda instalación con trabajadores');
    expect(r.obligatorias[0].nivel).toBe('directa');
  });

  it('un estado desconocido cae en el más conservador, no en «con normativa»', () => {
    // Si un valor nuevo del backend cayera en `con_normativa`, la pantalla
    // mostraría dos listas vacías sin ninguna advertencia — el peor resultado
    // posible de los tres.
    expect(mapearNormativa({ estado: 'algo_nuevo' }).estado).toBe('sin_perfil');
  });

  it('una respuesta rota no se lee como «sin obligaciones»', () => {
    expect(mapearNormativa(null)).toEqual(NORMATIVA_VACIA);
    expect(mapearNormativa(undefined).estado).toBe('sin_perfil');
    expect(mapearNormativa({ obligatorias: 'no es lista' }).obligatorias).toEqual([]);
  });

  it('el motivo ausente queda en null, no en cadena vacía', () => {
    // `''` se renderiza como un separador colgando; `null` la pantalla lo omite.
    const r = mapearNormativa({
      estado: 'con_normativa',
      obligatorias: [{ norm_id: 'n1', applicability_level: 'directa' }],
    });
    expect(r.obligatorias[0].motivo).toBeNull();
  });
});

describe('qué obliga y qué se propone', () => {
  it('solo la aplicación directa obliga', () => {
    // Tratar `indirecta` como obligatoria convertiría una sugerencia en una
    // obligación dentro de la matriz de la empresa.
    expect(esObligatoria('directa')).toBe(true);
    expect(esObligatoria('indirecta')).toBe(false);
    expect(esObligatoria('referencial')).toBe(false);
  });

  it('un nivel desconocido no obliga', () => {
    expect(esObligatoria('inventado')).toBe(false);
  });
});

describe('normas desactualizadas', () => {
  it('conserva el conteo de evaluaciones sobre la versión anterior', () => {
    // No es trabajo perdido: esas evaluaciones son la respuesta correcta ante
    // una auditoría del período en que se hicieron. El número dimensiona el
    // esfuerzo de revisar.
    const n = mapearDesactualizada({
      matrix_norm_id: 'mn1',
      norm_id: 'n1',
      title: 'DS 594',
      version_evaluada: 'v1',
      version_vigente: 'v2',
      evaluaciones_sobre_la_anterior: 42,
    });

    expect(n.evaluacionesSobreLaAnterior).toBe(42);
    expect(n.versionEvaluada).not.toBe(n.versionVigente);
  });

  it('un campo ausente no rompe la fila', () => {
    expect(mapearDesactualizada({}).evaluacionesSobreLaAnterior).toBe(0);
  });
});

describe('cuál matriz se mira', () => {
  it('la del período más reciente, no la que venga primero', () => {
    // El orden que devuelve la API no está garantizado. Avisar sobre la matriz
    // del año pasado mientras se mira la de este es peor que no avisar: manda
    // a revisar normas que en la matriz vigente ya están al día.
    expect(
      matrizMasReciente([
        { id: 'vieja', period_year: 2025 },
        { id: 'nueva', period_year: 2026 },
      ]),
    ).toBe('nueva');
  });

  it('sin matrices devuelve null, que es un estado normal', () => {
    // Una empresa recién creada todavía no generó su matriz. No es un error.
    expect(matrizMasReciente([])).toBeNull();
    expect(matrizMasReciente(null)).toBeNull();
  });
});
