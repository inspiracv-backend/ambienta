import { describe, expect, it } from 'vitest';
import { generateDynamicPassword, generateMockRut } from './rut';

/**
 * S-02 / RF-02 y RF-07: al usar el link especial el sistema asigna RUT y clave
 * dinámica automáticamente. Estas son las dos credenciales que ve el Cliente
 * Invitado, así que su formato importa: si el RUT no es válido, el flujo de
 * registro permanente (RF-03, que hace el Admin Empresa) parte con basura.
 */

/** Módulo 11, el mismo algoritmo que valida el Registro Civil. */
function digitoVerificadorEsValido(rutCompleto: string): boolean {
  const limpio = rutCompleto.replace(/\./g, '').replace(/-/g, '');
  const cuerpo = limpio.slice(0, -1);
  const dv = limpio.slice(-1).toUpperCase();

  let suma = 0;
  let multiplicador = 2;
  for (let i = cuerpo.length - 1; i >= 0; i--) {
    suma += Number(cuerpo[i]) * multiplicador;
    multiplicador = multiplicador === 7 ? 2 : multiplicador + 1;
  }

  const resto = 11 - (suma % 11);
  const esperado = resto === 11 ? '0' : resto === 10 ? 'K' : String(resto);
  return dv === esperado;
}

describe('generateMockRut', () => {
  it('genera un RUT con formato chileno (puntos y guion)', () => {
    expect(generateMockRut()).toMatch(/^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$/);
  });

  it('genera un dígito verificador aritméticamente válido', () => {
    // Se repite porque el RUT es aleatorio: un solo caso podría pasar por azar.
    for (let i = 0; i < 50; i++) {
      const rut = generateMockRut();
      expect(digitoVerificadorEsValido(rut), `RUT inválido generado: ${rut}`).toBe(true);
    }
  });

  it('no repite siempre el mismo RUT', () => {
    const generados = new Set(Array.from({ length: 20 }, () => generateMockRut()));
    expect(generados.size).toBeGreaterThan(1);
  });
});

describe('generateDynamicPassword', () => {
  it('genera una clave no vacía', () => {
    expect(generateDynamicPassword().length).toBeGreaterThan(0);
  });

  it('genera claves distintas en llamadas sucesivas', () => {
    const claves = new Set(Array.from({ length: 20 }, () => generateDynamicPassword()));
    expect(claves.size).toBeGreaterThan(1);
  });
});
