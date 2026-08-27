/**
 * El día que se perdía por el camino.
 *
 * Se encontró **en el navegador**, no acá: la API guardaba `2026-08-27` en
 * `valid_from` y la pantalla decía "Rige desde 26 ago 2026". Ninguna prueba de
 * unidad lo habría visto, porque el error no está en el dato ni en la API —
 * está en cómo el navegador interpreta una cadena de sólo fecha.
 */
import { describe, expect, it } from 'vitest';
import { fecha, fechaCalendario, fechaDeInstante } from './fechas';

describe('una fecha de calendario', () => {
  it('NO retrocede un día', () => {
    // `new Date('2026-08-27')` es medianoche **UTC**, y en Chile —UTC−4— eso
    // es el 26 a las 20:00. Con `toLocaleDateString` salía "26 ago 2026".
    expect(fechaCalendario('2026-08-27')).toBe('27 ago 2026');
    expect(fecha('2026-08-27')).toBe('27 ago 2026');
  });

  it('el primero de enero sigue siendo del año que es', () => {
    // El caso peor: retroceder un día cambia también el año, y una vigencia
    // que empieza el 1 de enero de 2027 aparecería como de 2026.
    expect(fecha('2027-01-01')).toBe('01 ene 2027');
  });

  it('no depende del huso de quien mire', () => {
    // Este es el punto: la misma cadena da lo mismo en Santiago, en Madrid y
    // en Tokio, porque no pasa por `Date`.
    expect(fechaCalendario('2026-12-31')).toBe('31 dic 2026');
  });

  it('una cadena rara se devuelve tal cual, sin inventar', () => {
    expect(fechaCalendario('no-es-fecha')).toBe('no-es-fecha');
  });
});

describe('una marca de tiempo', () => {
  it('se distingue de una fecha sola por su FORMA, no por el nombre del campo', () => {
    // Elegir por la forma es lo que hace que esto no se pueda usar mal: quien
    // escriba `fecha(rev.rigeDesde)` acierta sin acordarse de qué columna es
    // fecha y cuál es instante.
    expect(fecha('2026-08-27T00:00:00Z')).toBe(fechaDeInstante('2026-08-27T00:00:00Z'));
    expect(fecha('2026-08-27')).toBe(fechaCalendario('2026-08-27'));
  });

  it('un instante del mediodía UTC cae el mismo día en Chile', () => {
    expect(fechaDeInstante('2026-08-27T18:59:16Z')).toBe('27 ago 2026');
  });
});

describe('lo que falta', () => {
  it('nulo y vacío no imprimen "Invalid Date"', () => {
    expect(fecha(null)).toBe('—');
    expect(fecha(undefined)).toBe('—');
    expect(fecha('')).toBe('—');
  });
});
