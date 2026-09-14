import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { visibleEnAlcance } from './alcance';

const PLANTAS = [{ id: 'p-calama' }, { id: 'p-antofagasta' }];

describe('visibleEnAlcance', () => {
  it('una fila sin planta es de toda la empresa: se ve', () => {
    expect(visibleEnAlcance('', PLANTAS)).toBe(true);
    expect(visibleEnAlcance(null, PLANTAS)).toBe(true);
    expect(visibleEnAlcance(undefined, PLANTAS)).toBe(true);
  });

  it('una fila de una planta del alcance se ve', () => {
    expect(visibleEnAlcance('p-calama', PLANTAS)).toBe(true);
  });

  it('una fila de otra planta no', () => {
    expect(visibleEnAlcance('p-rancagua', PLANTAS)).toBe(false);
  });

  it('sin plantas cargadas, lo de toda la empresa se sigue viendo', () => {
    expect(visibleEnAlcance('', [])).toBe(true);
    expect(visibleEnAlcance('p-calama', [])).toBe(false);
  });
});

/**
 * El filtro viejo no vuelve.
 *
 * Estaba copiado en seis pantallas; arreglar cinco habría dejado la sexta
 * escondiendo las filas sin planta. Se barre el código en vez de confiar en que
 * nadie lo vuelva a escribir.
 */
describe('ninguna pantalla filtra por planta a mano', () => {
  function archivos(dir: string): string[] {
    return readdirSync(dir).flatMap((nombre) => {
      const ruta = join(dir, nombre);
      if (statSync(ruta).isDirectory()) return nombre === 'node_modules' ? [] : archivos(ruta);
      return /\.tsx?$/.test(nombre) && !/\.test\.tsx?$/.test(nombre) ? [ruta] : [];
    });
  }

  it('usa visibleEnAlcance y no `plantas.some((p) => p.id === x.plantId)`', () => {
    const raiz = join(__dirname, '..');
    const patron = /\.some\(\(\w+\) => \w+\.id === \w+\.plantId\)/;
    const culpables = [...archivos(join(raiz, 'app')), ...archivos(join(raiz, 'components'))].filter((f) =>
      patron.test(readFileSync(f, 'utf-8')),
    );
    expect(culpables).toEqual([]);
  });
});
