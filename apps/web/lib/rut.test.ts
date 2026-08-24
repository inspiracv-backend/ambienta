import { describe, expect, it } from 'vitest';
import { normalizarRut, validarRut, generateMockRut, generateDynamicPassword } from './rut';

/**
 * El RUT, en TypeScript. **Gemelo de `apps/api/tests/test_rut.py`.**
 *
 * Los dos archivos comparten los mismos casos, con los mismos valores. Es
 * deliberado y es lo único que impide que las dos implementaciones se
 * desincronicen: no pueden importarse entre sí, así que la sincronía depende de
 * que los dos lados se prueben contra lo mismo.
 *
 * **Si difieren, un RUT válido en la pantalla es inválido en la API** — y la
 * persona ve "RUT incorrecto" sobre un RUT que es suyo, un fallo que se lee
 * como un error de quien escribe y no del sistema.
 *
 * Al agregar un caso acá, agregarlo allá. La tabla de abajo está duplicada
 * literal a propósito, para que la comparación sea visual.
 */

/** Mismos valores que `VALIDOS` en el gemelo de Python. */
const VALIDOS: Array<[string, string]> = [
  ['12345678-5', '12345678-5'],
  ['12.345.678-5', '12345678-5'],
  ['123456785', '12345678-5'],
  ['11111111-1', '11111111-1'],
  ['22222222-2', '22222222-2'],
  ['5126663-3', '5126663-3'],
  // El verificador K, **calculado, no elegido de memoria**. La primera versión
  // de esta tabla traía valores inventados y las pruebas los delataron.
  ['1000005-K', '1000005-K'],
  ['1000005-k', '1000005-K'],
  // Y el verificador 0, el otro caso que no es un resto directo.
  ['1000013-0', '1000013-0'],
];

/** Mismos valores que `INVALIDOS` en el gemelo de Python. */
const INVALIDOS = [
  '12345678-4', // verificador que no cierra
  '',
  '-',
  '5',
  'abcdefgh-1',
  '12345678-X', // X no es un verificador posible
  '0-0', // cuerpo vacío tras quitar ceros
];

describe('normalizar', () => {
  it.each(VALIDOS)('los tres formatos dan lo mismo: %s', (entrada, esperado) => {
    // Sin esto, "este RUT ya está en uso" no encuentra el duplicado: el mismo
    // RUT con puntos, sin puntos y sin guion son tres cadenas para la base.
    expect(normalizarRut(entrada)).toBe(esperado);
  });

  it('los ceros a la izquierda no hacen otro RUT', () => {
    // `01.234.567-4` y `1.234.567-4` son la misma persona. Guardarlos distinto
    // la volvería dos.
    expect(normalizarRut('01234567-4')).toBe(normalizarRut('1234567-4'));
  });

  it('la K minúscula se guarda mayúscula', () => {
    expect(normalizarRut('1000005-k')).toBe('1000005-K');
  });

  it('un verificador imposible no se normaliza', () => {
    // `X` no es un verificador que exista, así que la cadena no es un RUT. Se
    // rechaza acá, al interpretar, y no sólo al validar el módulo 11: si
    // pasara, cualquier cosa terminada en letra quedaría guardada como si
    // tuviera formato correcto.
    expect(normalizarRut('12345678-X')).toBeNull();
    expect(normalizarRut('12345678-Z')).toBeNull();
  });

  it('lo que no se puede interpretar da null y no lanza', () => {
    // **No lanza a propósito.** Quien llama está validando lo que alguien
    // escribió; una excepción ahí obliga a envolver cada uso en un try.
    for (const malo of ['', '-', 'abc', '   ']) {
      expect(normalizarRut(malo)).toBeNull();
    }
  });
});

describe('validar', () => {
  it.each(VALIDOS)('acepta %s', (entrada) => {
    expect(validarRut(entrada)).toBe(true);
  });

  it.each(INVALIDOS)('rechaza %s', (entrada) => {
    expect(validarRut(entrada)).toBe(false);
  });

  it('un verificador cambiado por uno lo invalida', () => {
    // Es para lo que sirve el módulo 11: detectar el dígito tipeado mal. Sin
    // esa comprobación, un error de tipeo crea una credencial que no le
    // corresponde a nadie y que nadie puede reclamar.
    expect(validarRut('12345678-5')).toBe(true);
    expect(validarRut('12345678-6')).toBe(false);
  });

  it('el verificador sólo dice que el número cierra', () => {
    // **No prueba que el RUT sea de quien lo escribe.** Queda como prueba
    // porque es la limitación que importa cuando el RUT es credencial, y hoy
    // nada más la cubre.
    expect(validarRut('11111111-1')).toBe(true);
  });
});

describe('lo que se genera para el Cliente Invitado', () => {
  it('el RUT generado siempre pasa su propia validación', () => {
    // Si no, la pantalla mostraría al invitado un RUT que la API le rechaza —
    // y el invitado no tiene forma de saber que el sistema se lo dio mal.
    for (let i = 0; i < 200; i++) {
      expect(validarRut(generateMockRut())).toBe(true);
    }
  });

  it('la clave dinámica no usa caracteres que se confunden al leerse', () => {
    // Se dicta por teléfono y se copia a mano: `O`/`0` e `I`/`1` generan
    // intentos fallidos que parecen clave equivocada.
    const prohibidos = /[O0I1]/;
    for (let i = 0; i < 200; i++) {
      expect(generateDynamicPassword()).not.toMatch(prohibidos);
    }
  });

  it('la clave tiene largo fijo', () => {
    expect(generateDynamicPassword()).toHaveLength(6);
  });
});
