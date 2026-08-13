import { describe, expect, it } from 'vitest';
import { leerTenantSettings, LIMITE_USUARIOS_POR_DEFECTO } from '@ambienta/shared';

/**
 * `settings` es un jsonb: la base acepta cualquier cosa, incluidas empresas
 * creadas antes de que existiera este esquema y claves escritas a mano.
 *
 * La propiedad que importa: **una clave invalida no debe tumbar la carga de la
 * empresa entera**. Si un dato podrido dejara la pantalla en blanco, migrar
 * exigiria arreglar todas las filas antes de desplegar.
 */
describe('leerTenantSettings', () => {
  it('lee las tres claves conocidas', () => {
    const r = leerTenantSettings({
      limiteUsuarios: 250,
      modulosActivos: ['auditorias'],
      logoUrl: 'https://ejemplo.cl/logo.png',
    });

    expect(r.limiteUsuarios).toBe(250);
    expect(r.modulosActivos).toEqual(['auditorias']);
    expect(r.logoUrl).toBe('https://ejemplo.cl/logo.png');
  });

  it('descarta una clave invalida y conserva las validas', () => {
    // Lo que permite ir migrando sin arreglar todas las filas primero.
    const r = leerTenantSettings({
      limiteUsuarios: 'muchos',
      modulosActivos: ['auditorias'],
    });

    expect(r.limiteUsuarios).toBeUndefined();
    expect(r.modulosActivos).toEqual(['auditorias']);
  });

  it('descarta un modulo que no existe en el catalogo', () => {
    const r = leerTenantSettings({ modulosActivos: ['modulo-inventado'] });
    expect(r.modulosActivos).toBeUndefined();
  });

  it('descarta un logo que no es una URL', () => {
    expect(leerTenantSettings({ logoUrl: 'no-es-una-url' }).logoUrl).toBeUndefined();
  });

  it('ignora claves que el esquema no declara', () => {
    // Si alguien escribio algo a mano, no viaja de vuelta al guardar.
    const r = leerTenantSettings({ limiteUsuarios: 10, algoViejo: 'x' });
    expect(r).toEqual({ limiteUsuarios: 10 });
  });

  it('tolera null, undefined y formas que no son objeto', () => {
    for (const entrada of [null, undefined, 'texto', 42, ['a']]) {
      expect(leerTenantSettings(entrada)).toEqual({});
    }
  });

  it('un limite de cero o negativo no es valido', () => {
    // El tope de usuarios de un contrato no puede ser cero: seria una empresa
    // que no puede tener a nadie dentro.
    expect(leerTenantSettings({ limiteUsuarios: 0 }).limiteUsuarios).toBeUndefined();
    expect(leerTenantSettings({ limiteUsuarios: -5 }).limiteUsuarios).toBeUndefined();
  });

  it('expone el valor por defecto para quien no tiene tope propio', () => {
    expect(LIMITE_USUARIOS_POR_DEFECTO).toBe(50);
  });
});
