/**
 * `getTodas`: una lista que tiene que estar completa para decir la verdad.
 *
 * La API corta cada listado en 100 si no se le pide otra cosa y avisa con
 * `X-Has-More`. Medido el 21-sep: la Matriz Legal leia 100 de las 264
 * evaluaciones de la empresa y mostraba las otras 164 como "sin evaluar".
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, TOPE_DE_PAGINA } from './api-client';

function respuesta(filas: unknown[], hayMas: boolean) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(filas),
    headers: { get: (h: string) => (h === 'X-Has-More' && hayMas ? 'true' : null) },
  };
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('leer un listado entero', () => {
  it('pide pagina tras pagina hasta que la API deja de avisar que hay mas', async () => {
    const primera = Array.from({ length: TOPE_DE_PAGINA }, (_, i) => ({ i }));
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(respuesta(primera, true))
      .mockResolvedValueOnce(respuesta([{ i: 'ultima' }], false));
    vi.stubGlobal('fetch', fetch);

    const filas = await api.getTodas('/compliance/article-compliance');

    expect(filas).toHaveLength(TOPE_DE_PAGINA + 1);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(String(fetch.mock.calls[0][0])).toContain(`/compliance/article-compliance?limit=${TOPE_DE_PAGINA}&skip=0`);
    expect(String(fetch.mock.calls[1][0])).toContain(`limit=${TOPE_DE_PAGINA}&skip=${TOPE_DE_PAGINA}`);
  });

  it('respeta la consulta que ya traia la ruta', async () => {
    const fetch = vi.fn().mockResolvedValue(respuesta([], false));
    vi.stubGlobal('fetch', fetch);

    await api.getTodas('/audits/?estado=abierta');

    expect(String(fetch.mock.calls[0][0])).toContain(`/audits/?estado=abierta&limit=${TOPE_DE_PAGINA}&skip=0`);
  });

  it('si no termina nunca, falla en vez de devolver una lista a medias como si estuviera completa', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta([{}], true)));

    await expect(api.getTodas('/notifications/')).rejects.toThrow(/no se puede cargar entera/);
  });
});

describe('un get de listado', () => {
  it('si la API corto una lista que nadie pidio cortar, trae el resto', async () => {
    // Asi se leian las obligaciones, los usuarios, las auditorias... con `get`
    // pelado. Iban en 81 obligaciones: una empresa real pasa de 100 enseguida.
    const primera = Array.from({ length: 100 }, (_, i) => ({ i }));
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(respuesta(primera, true))
      .mockResolvedValueOnce(respuesta([{ i: 100 }, { i: 101 }], false));
    vi.stubGlobal('fetch', fetch);

    const filas = await api.get<unknown[]>('/obligations/');

    expect(filas).toHaveLength(102);
    expect(String(fetch.mock.calls[1][0])).toContain(`/obligations/?limit=${TOPE_DE_PAGINA}&skip=100`);
  });

  it('quien pidio un limite recibe esa pagina y nada mas', async () => {
    const fetch = vi.fn().mockResolvedValue(respuesta([{ i: 0 }], true));
    vi.stubGlobal('fetch', fetch);

    const filas = await api.get<unknown[]>('/documents/?limit=1');

    expect(filas).toHaveLength(1);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('un recurso suelto no se toca', async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: 'a' }),
      headers: { get: () => null },
    });
    vi.stubGlobal('fetch', fetch);

    await expect(api.get('/audits/a')).resolves.toEqual({ id: 'a' });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

