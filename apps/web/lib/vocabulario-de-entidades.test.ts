/**
 * El puente entre el nombre en español y el que entiende la API.
 *
 * ## Por qué esta prueba existe
 *
 * Porque el modo de fallo es **silencioso**: si alguien agrega un tipo al enum
 * `EntidadAuditable` y no lo mapea, la línea de tiempo de esa entidad no
 * consulta nada y la pantalla muestra «Sin movimientos registrados» — sobre un
 * registro que sí tiene historia guardada. Nadie ve un error; se ve un
 * registro sin actividad, que es una afirmación.
 *
 * Es la misma familia que las cinco listas de migraciones y que el guardián de
 * las etapas del CRM: dos listas que deben decir lo mismo, comparadas por una
 * máquina y no por la memoria de alguien.
 */
import { describe, expect, it } from 'vitest';
import { EntidadAuditableSchema } from '@ambienta/shared';
import {
  SIN_HISTORIA_EN_LA_API,
  TIPO_EN_LA_API,
  tipoEnLaApi,
} from './vocabulario-de-entidades';

const TODAS = EntidadAuditableSchema.options;

describe('cada entidad está decidida', () => {
  it('ninguna quedó sin mapear ni sin declarar', () => {
    const huerfanas = TODAS.filter(
      (e) => !(e in TIPO_EN_LA_API) && !(e in SIN_HISTORIA_EN_LA_API),
    );

    expect(huerfanas, {
      message:
        `Estas entidades no están mapeadas a la API ni declaradas sin historia: ` +
        `${huerfanas.join(', ')}. Su línea de tiempo diría «sin movimientos» ` +
        `sobre registros con actividad guardada, sin ningún error a la vista.`,
    } as never).toEqual([]);
  });

  it('ninguna está en las dos listas', () => {
    // Estar en las dos sería una contradicción que se resolvería por el orden
    // de lectura, o sea por accidente.
    const dobles = TODAS.filter(
      (e) => e in TIPO_EN_LA_API && e in SIN_HISTORIA_EN_LA_API,
    );
    expect(dobles).toEqual([]);
  });

  it('las declaradas sin historia traen su motivo, no una marca vacía', () => {
    // Un `''` convertiría la lista en un cajón donde tirar lo que no se quiso
    // pensar. El motivo es lo que distingue una decisión de un olvido.
    for (const [entidad, motivo] of Object.entries(SIN_HISTORIA_EN_LA_API)) {
      expect(motivo, `«${entidad}» está sin historia y sin explicar por qué`).toBeTruthy();
      expect((motivo as string).length).toBeGreaterThan(30);
    }
  });
});

describe('la traducción', () => {
  it('el español de la aplicación se convierte al dominio de la API', () => {
    // Los tres nombres de la misma cosa: `obligacion` acá, `obligation` en la
    // API, `obligations` en `audit_log`. El tercero lo resuelve el servidor.
    expect(tipoEnLaApi('obligacion')).toBe('obligation');
    expect(tipoEnLaApi('no_conformidad')).toBe('nonconformity');
    expect(tipoEnLaApi('norma')).toBe('legal_norm');
  });

  it('una entidad sin equivalente devuelve null, no un tipo inventado', () => {
    // `null` hace que el hook no consulte. Devolver el nombre en español
    // produciría un 422 en cada carga de la ficha de un usuario.
    expect(tipoEnLaApi('usuario')).toBeNull();
    expect(tipoEnLaApi('tenant')).toBeNull();
  });
});
