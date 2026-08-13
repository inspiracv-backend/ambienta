import { describe, expect, it } from 'vitest';
import { ApiError, mensajeDeError } from './api-client';

/**
 * `detail` de FastAPI llega en dos formas segun quien rechaza, y la segunda es
 * la que se veia mal: los 422 de Pydantic traen una **lista** de errores por
 * campo, y leerla como cadena imprime `[object Object]` en pantalla.
 */
describe('mensajeDeError', () => {
  it('usa el detail cuando la API manda una cadena', () => {
    const error = new ApiError(409, 'Conflict', { detail: 'Ya existe un proceso con ese codigo.' });
    expect(mensajeDeError(error)).toBe('Ya existe un proceso con ese codigo.');
  });

  it('arma el mensaje campo por campo cuando el detail es una lista', () => {
    const error = new ApiError(422, 'Unprocessable Entity', {
      detail: [
        { loc: ['body', 'code'], msg: 'Field required', type: 'missing' },
        { loc: ['body', 'process_type'], msg: 'Input should be a valid string' },
      ],
    });

    const mensaje = mensajeDeError(error);

    expect(mensaje).toContain('code: Field required');
    expect(mensaje).toContain('process_type: Input should be a valid string');
    // La prueba de que no se cayo al camino de cadena.
    expect(mensaje).not.toContain('[object Object]');
  });

  it('descarta el prefijo body del nombre del campo', () => {
    const error = new ApiError(422, 'Unprocessable Entity', {
      detail: [{ loc: ['body', 'norm_id'], msg: 'no es visible para esta empresa' }],
    });
    expect(mensajeDeError(error)).toBe('norm_id: no es visible para esta empresa');
  });

  it('cae a un mensaje por codigo cuando el detail no viene', () => {
    expect(mensajeDeError(new ApiError(409, 'Conflict', null))).toBe(
      'Ya existe un registro con ese valor.',
    );
    expect(mensajeDeError(new ApiError(403, 'Forbidden', {}))).toBe(
      'No tienes permiso para hacer esto.',
    );
    expect(mensajeDeError(new ApiError(500, 'Server Error', {}))).toContain('500');
  });

  it('distingue no haber llegado a la API de que la API rechace', () => {
    // Un TypeError es lo que lanza fetch cuando no hay red: no es un ApiError,
    // y decir "el servidor rechazo" seria mentira — no hubo servidor.
    expect(mensajeDeError(new TypeError('Failed to fetch'))).toContain('contactar al servidor');
  });

  it('ignora una lista de detalles vacia en vez de devolver cadena vacia', () => {
    const error = new ApiError(422, 'Unprocessable Entity', { detail: [] });
    expect(mensajeDeError(error).length).toBeGreaterThan(0);
  });
});
