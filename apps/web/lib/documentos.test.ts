import { describe, expect, it } from 'vitest';
import { File as NodeFile } from 'node:buffer';
import { sha256DelArchivo } from './documentos';

/**
 * La huella del archivo se calcula en el navegador (RF-110).
 *
 * ## Por qué acá y no en el servidor
 *
 * Con enlaces firmados el archivo **va directo al bucket**: la API nunca lo
 * ve, así que no puede calcularle nada. Y el hash tiene que existir *antes* de
 * subir para poder viajar dentro de la firma — es lo que permite que Backblaze
 * compruebe el contenido y **rechace la subida** si no corresponde.
 *
 * Esa es la diferencia entre un hash verificado y uno afirmado: si lo
 * mandáramos después, estaríamos declarando qué creemos que subimos.
 */

/**
 * Un `File` de verdad, no el de jsdom.
 *
 * **jsdom no implementa `File.arrayBuffer()`**, que es lo que usa la función
 * bajo prueba. Con el `File` de jsdom estas pruebas fallarían por una carencia
 * del entorno y no por el código — y el error, `arrayBuffer is not a
 * function`, se lee como si la implementación estuviera mal.
 *
 * El de Node lo implementa y es el mismo estándar que el navegador.
 */
function archivo(contenido: string, nombre = 'acta.pdf'): File {
  return new NodeFile([contenido], nombre, { type: 'application/pdf' }) as unknown as File;
}

describe('sha256DelArchivo', () => {
  it('devuelve el SHA-256 conocido de un contenido conocido', async () => {
    // El SHA-256 de la cadena vacía es un valor público y verificable, así que
    // sirve de ancla: si la implementación cambiara de algoritmo o de
    // codificación, esto se pone rojo con un valor que cualquiera puede
    // contrastar.
    expect(await sha256DelArchivo(archivo(''))).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    );
  });

  it('devuelve hexadecimal en minúscula de 64 caracteres', async () => {
    // La columna de la base es `char(64)`, que es justo lo que mide un SHA-256
    // en hex. En base64 mide 44 y **entraría igual**, rellenado y sin fallar.
    const hash = await sha256DelArchivo(archivo('acta de inspección'));

    expect(hash).toMatch(/^[0-9a-f]{64}$/);
  });

  it('dos contenidos distintos dan huellas distintas', async () => {
    const uno = await sha256DelArchivo(archivo('versión 1'));
    const dos = await sha256DelArchivo(archivo('versión 2'));

    expect(uno).not.toBe(dos);
  });

  it('el mismo contenido con otro nombre da la MISMA huella', async () => {
    // La huella es del contenido, no del archivo. Importa porque una revisión
    // renombrada no es una revisión nueva, y quien audita compara el contenido.
    const uno = await sha256DelArchivo(archivo('mismo texto', 'a.pdf'));
    const dos = await sha256DelArchivo(archivo('mismo texto', 'b.pdf'));

    expect(uno).toBe(dos);
  });
});
