'use client';

import { useSyncExternalStore } from 'react';

/**
 * Si la API dijo que esta sesión **no tiene empresa** (`403 sesion_sin_empresa`).
 *
 * ## Por qué existe
 *
 * Quien entra con Google o Microsoft sin haber sido dado de alta tiene una
 * sesión válida en Clerk, pero ningún `tenant_id`: la API le responde 403 en
 * **todo**. Hasta el 14-sep la web no distinguía ese 403 de los demás, así que
 * la persona veía errores en cada pantalla, sin explicación y **sin forma de
 * salir** — la sesión sobrevive al refresco, y mandarla al ingreso arma un bucle
 * porque `<SignIn />` la ve adentro y la devuelve al tablero.
 *
 * Es un estado de módulo y no de un provider porque lo escribe `api-client`,
 * que no es un componente.
 */

let sinEmpresa = false;
const suscriptores = new Set<() => void>();

export function marcarSesionSinEmpresa(valor: boolean) {
  if (sinEmpresa === valor) return;
  sinEmpresa = valor;
  suscriptores.forEach((avisar) => avisar());
}

function suscribir(avisar: () => void) {
  suscriptores.add(avisar);
  return () => suscriptores.delete(avisar);
}

export function useSesionSinEmpresa(): boolean {
  return useSyncExternalStore(suscribir, () => sinEmpresa, () => false);
}

/** El código con que la API marca este 403. Se decide por el código, nunca por el mensaje. */
export const CODIGO_SIN_EMPRESA = 'sesion_sin_empresa';

export function esSinEmpresa(status: number, cuerpo: unknown): boolean {
  if (status !== 403) return false;
  const detail = (cuerpo as { detail?: unknown } | null)?.detail;
  return typeof detail === 'object' && detail !== null && (detail as { codigo?: unknown }).codigo === CODIGO_SIN_EMPRESA;
}
