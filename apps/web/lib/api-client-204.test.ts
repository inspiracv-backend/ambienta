/**
 * Una respuesta sin cuerpo, que rompía **todos los borrados**.
 *
 * `204 No Content` + `res.json()` lanza `SyntaxError: Unexpected end of JSON
 * input`. Todos los `DELETE` de la API responden 204, así que cada borrado de
 * la aplicación se leía como fallido: la fila desaparecía de la base, la
 * pantalla mostraba un error y no recargaba, y quien lo hizo veía el registro
 * seguir ahí. Reintentar daba 404, que se lee como "esto está roto".
 *
 * Se encontró **manejando la pantalla**, no leyendo el código: se borró un
 * equipo desde la tabla de equipos regulados y se comparó con la API. El
 * `DELETE` respondió 204, la lista devolvió 2 elementos y la tabla seguía
 * mostrando 3.
 *
 * Va en su propio archivo porque no habla de errores: habla de una respuesta
 * correcta que se estaba leyendo mal.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './api-client';

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('una respuesta sin cuerpo', () => {
  it('un 204 devuelve null en vez de reventar', async () => {
    const json = vi.fn().mockRejectedValue(new SyntaxError('Unexpected end of JSON input'));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 204, json }));

    await expect(api.delete('/iso14001/equipment/abc')).resolves.toBeNull();
    // Y ni siquiera se intenta leer el cuerpo: llamar a `json()` sobre un 204
    // es la operación que lanza.
    expect(json).not.toHaveBeenCalled();
  });

  it('un 205 tampoco trae cuerpo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 205,
        json: () => Promise.reject(new SyntaxError('vacío')),
      }),
    );
    await expect(api.get('/lo-que-sea')).resolves.toBeNull();
  });

  it('un 200 con cuerpo se sigue leyendo', async () => {
    /**
     * La guarda mira **el estado**, no el cuerpo ni `content-length`: un 204
     * puede venir sin esa cabecera, y algunos proxys la ponen en 0 para
     * respuestas que sí traen algo. Mirando el cuerpo, una respuesta legítima
     * vacía y una con datos se tratarían igual.
     */
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({ id: 'x' }) }),
    );

    await expect(api.get('/iso14001/equipment')).resolves.toEqual({ id: 'x' });
  });

  it('un 201 con el recurso creado se sigue leyendo', async () => {
    // `POST` responde 201 **con cuerpo**. Si la guarda se ampliara a "2xx sin
    // contenido conocido", las altas dejarían de devolver lo creado y las
    // pantallas no sabrían el id de lo que acaban de crear.
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue({ ok: true, status: 201, json: () => Promise.resolve({ id: 'nuevo' }) }),
    );

    await expect(api.post('/iso14001/equipment', {})).resolves.toEqual({ id: 'nuevo' });
  });
});
