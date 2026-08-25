/**
 * El RUT: validarlo, normalizarlo y darle formato.
 *
 * Es credencial de acceso —el Cliente Invitado entra con RUT y clave (RF-01,
 * RF-02), y quien entro por Google puede fijar una clave local asociada a su
 * RUT (RF-06)— y ademas dato de negocio que aparece en informes.
 *
 * ## El mismo calculo esta escrito dos veces, a proposito
 *
 * El gemelo vive en `apps/api/app/rut.py`. No pueden importarse entre si, asi
 * que la sincronia es manual — **y este repositorio ya se quemo con eso**: hubo
 * codigo leyendo columnas que no existian sin que nada lo detectara.
 *
 * Aca el riesgo es peor que una columna: si las dos implementaciones difieren,
 * **un RUT valido en la pantalla es invalido en la API**, y la persona ve
 * "RUT incorrecto" sobre un RUT que es suyo. Por eso los dos lados comparten
 * los mismos casos de prueba, incluido el verificador `K`.
 */

function computeDv(rut: number): string {
  let sum = 0;
  let multiplier = 2;
  let n = rut;
  while (n > 0) {
    sum += (n % 10) * multiplier;
    n = Math.floor(n / 10);
    multiplier = multiplier === 7 ? 2 : multiplier + 1;
  }
  const remainder = 11 - (sum % 11);
  if (remainder === 11) return '0';
  if (remainder === 10) return 'K';
  return String(remainder);
}

function formatRut(rut: number, dv: string): string {
  const reversedDigits = String(rut).split('').reverse();
  const groups: string[] = [];
  for (let i = 0; i < reversedDigits.length; i += 3) {
    groups.push(reversedDigits.slice(i, i + 3).reverse().join(''));
  }
  return `${groups.reverse().join('.')}-${dv}`;
}

/** Solo los digitos y el verificador, sin puntos ni guion. */
function soloDigitos(rut: string): string {
  return rut.replace(/[.\-\s]/g, '').toUpperCase();
}

/**
 * El RUT en su forma canonica: `12345678-K`, sin puntos.
 *
 * **Se guarda normalizado, no como lo escribio la persona.** El mismo RUT se
 * escribe de tres formas —`12.345.678-5`, `12345678-5`, `123456785`— y sin
 * normalizar, la comprobacion de "este RUT ya esta en uso" no encuentra el
 * duplicado: son tres cadenas distintas para la base.
 *
 * Devuelve `null` si no se puede interpretar. **No lanza**: quien llama suele
 * estar validando lo que alguien escribio, y una excepcion ahi obliga a
 * envolver cada uso en un try.
 */
export function normalizarRut(rut: string): string | null {
  const limpio = soloDigitos(rut ?? '');
  if (limpio.length < 2) return null;

  const cuerpo = limpio.slice(0, -1);
  const dv = limpio.slice(-1);
  if (!/^\d+$/.test(cuerpo)) return null;
  if (!/^[0-9K]$/.test(dv)) return null;

  // Se quitan los ceros a la izquierda: `01.234.567-4` y `1.234.567-4` son el
  // mismo RUT, y guardarlos distinto los volveria dos personas.
  const sinCeros = cuerpo.replace(/^0+/, '');
  if (!sinCeros) return null;

  return `${sinCeros}-${dv}`;
}

/**
 * Si el RUT es valido: se puede interpretar **y** su digito verificador cierra.
 *
 * El verificador es lo unico que se puede comprobar sin consultar al Registro
 * Civil. **No prueba que el RUT sea de quien lo escribe** —solo que no es un
 * numero inventado al azar— y esa distincion importa cuando el RUT es
 * credencial de acceso.
 */
export function validarRut(rut: string): boolean {
  const normalizado = normalizarRut(rut);
  if (normalizado === null) return false;

  const [cuerpo, dv] = normalizado.split('-');
  return computeDv(Number(cuerpo)) === dv;
}

/**
 * `generateMockRut()` y `generateDynamicPassword()` **se quitaron el
 * 25-ago-2026**, cuando la emisión pasó al servidor (`POST
 * /acceso-invitado/{empresa}/credenciales`).
 *
 * No se dejaron «por si acaso», y esa es la decisión: mientras existieran, la
 * pantalla podía volver a llamarlas y quedaría igual de convincente que antes
 * —credenciales de aspecto correcto, dígito verificador válido— **sin que
 * existieran en la base**. Es el modo de fallo que ya ocurrió una vez acá.
 *
 * Un RUT de invitado ahora lo asigna la API, que además garantiza lo que el
 * navegador no puede: que no choque con el de otra persona de esa empresa.
 */
