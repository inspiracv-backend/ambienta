import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, codigoDeError } from './api-client';
import { consultarAlAsistente, mensajeDeFalla, valeLaPenaReintentar } from './chatbot';

/**
 * El cliente del asistente: qué se manda y cómo se lee lo que vuelve.
 *
 * El navegador **no habla con el AI Service**; habla con la fachada de la API.
 * Lo que se comprueba acá es eso: la ruta, lo que viaja en el cuerpo, y que
 * "no está configurado" no se confunda con "se cayó".
 */

const post = vi.fn();
vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return { ...real, api: { post: (...a: unknown[]) => post(...a) } };
});

const RESPUESTA = {
  conversation_id: 'c-1',
  respuesta: 'La Ley 20.920 exige metas de valorización.',
  se_abstuvo: false,
  citas: [],
  guardado: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  post.mockResolvedValue(RESPUESTA);
});

describe('consultarAlAsistente', () => {
  it('pregunta a la fachada de la API, no al AI Service', async () => {
    await consultarAlAsistente({ pregunta: '¿Qué exige la Ley REP?' });

    expect(post).toHaveBeenCalledWith(
      '/support/chatbot/consulta',
      { pregunta: '¿Qué exige la Ley REP?' },
      { tenantId: undefined },
    );
  });

  it('la empresa viaja como cabecera, no en el cuerpo', async () => {
    /** **Sin Clerk no hay token** y `X-Tenant-Id` es lo unico que dice de que
     * empresa se pregunta: sin ella la API responde 401 — es lo que pasaba
     * hasta que esta pantalla se probo contra la API de verdad. Y va fuera del
     * cuerpo porque es una cabecera de desarrollo, no un parametro con el que
     * se elige empresa. */
    await consultarAlAsistente({ pregunta: 'hola', tenantId: 'a0000000-0000-0000-0000-000000000001' });

    const [, cuerpo, opciones] = post.mock.calls[0] as [string, Record<string, unknown>, unknown];
    expect(opciones).toEqual({ tenantId: 'a0000000-0000-0000-0000-000000000001' });
    expect(Object.keys(cuerpo)).toEqual(['pregunta']);
  });

  it('no manda los opcionales vacíos', async () => {
    await consultarAlAsistente({ pregunta: 'hola', conversacionId: null });

    const [, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(Object.keys(cuerpo)).toEqual(['pregunta']);
  });

  it('manda la conversación cuando ya hay una, para que el hilo siga', async () => {
    await consultarAlAsistente({ pregunta: '¿y el plazo?', conversacionId: 'c-1' });

    expect(post).toHaveBeenCalledWith(
      '/support/chatbot/consulta',
      { pregunta: '¿y el plazo?', conversation_id: 'c-1' },
      { tenantId: undefined },
    );
  });

  it('manda la fecha para preguntar por el texto vigente entonces', async () => {
    await consultarAlAsistente({ pregunta: 'x', fecha: '2024-03-01' });

    expect(post).toHaveBeenCalledWith(
      '/support/chatbot/consulta',
      { pregunta: 'x', fecha: '2024-03-01' },
      { tenantId: undefined },
    );
  });

  it('no inventa empresa ni usuario en el cuerpo', async () => {
    /** Salen del token verificado. Un `tenant_id` acá sería un parámetro con
     * el que cualquiera elige de qué empresa leer. */
    await consultarAlAsistente({ pregunta: 'x', conversacionId: 'c-1', fecha: '2024-03-01' });

    const [, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(Object.keys(cuerpo).sort()).toEqual(['conversation_id', 'fecha', 'pregunta']);
  });
});

describe('leer el motivo del rechazo', () => {
  /** La API manda el código **dentro de `detail`**: es lo que hace FastAPI con
   * `HTTPException(detail={...})`. Leer sólo la raíz lo dejaba en "sin código". */
  const sinConfigurar = new ApiError(503, 'Service Unavailable', {
    detail: { codigo: 'ai_service_sin_configurar', mensaje: 'Falta AI_SERVICE_URL.' },
  });
  const noResponde = new ApiError(503, 'Service Unavailable', {
    detail: { codigo: 'ai_service_no_responde', mensaje: 'No responde.' },
  });

  it('encuentra el código aunque venga anidado', () => {
    expect(codigoDeError(sinConfigurar)).toBe('ai_service_sin_configurar');
  });

  it('sigue encontrando el que viene en la raíz', () => {
    expect(codigoDeError(new ApiError(409, 'Conflict', { codigo: 'valor_duplicado' }))).toBe(
      'valor_duplicado',
    );
  });

  it('un detail de texto no tiene código', () => {
    expect(codigoDeError(new ApiError(404, 'Not Found', { detail: 'no existe' }))).toBeNull();
  });

  it('distingue "todavía no está" de "no respondió"', () => {
    expect(mensajeDeFalla(sinConfigurar)).toContain('todavía no está disponible');
    expect(mensajeDeFalla(noResponde)).toContain('Vuelve a intentarlo');
  });

  it('insistir contra un servicio sin configurar no sirve, y se dice', () => {
    expect(valeLaPenaReintentar(sinConfigurar)).toBe(false);
    expect(valeLaPenaReintentar(noResponde)).toBe(true);
  });

  it('un rechazo cualquiera cae en el mensaje general', () => {
    expect(mensajeDeFalla(new ApiError(403, 'Forbidden', { detail: 'No tienes permiso.' }))).toBe(
      'No tienes permiso.',
    );
  });

  it('sin red tampoco se queda mudo', () => {
    expect(mensajeDeFalla(new TypeError('Failed to fetch'))).toContain('No se pudo contactar');
  });
});
