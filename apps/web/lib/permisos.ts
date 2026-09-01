import { api } from './api-client';

/**
 * Permisos: un solo vocabulario, el de la base (#217, RF-12).
 *
 * ## Por qué este archivo existe
 *
 * La pantalla de permisos tenía **su propia lista escrita a mano** de 13
 * claves (`matriz_legal.evaluar`, `obligaciones.crear`…) mientras la guarda de
 * la API decide con los 39 códigos de `permissions` (`legal_matrix.article.evaluate`,
 * `obligation.write`…). Medido el 1-sep-2026: **cero claves en común**.
 *
 * Lo único que había evitado el daño es que la pantalla nunca llegaba a
 * guardar — `updatePermisos` solo tocaba el estado local. Es decir, la razón de
 * que no hubiera un problema era que la función no funcionaba. El día que
 * alguien "conectara el endpoint que falta", un Admin Empresa habría marcado
 * trece casillas que el servidor no consulta nunca.
 *
 * ## Lo que este archivo NO hace
 *
 * **No traduce.** No hay un mapa de `matriz_legal.evaluar` a
 * `legal_matrix.article.evaluate` ni lo va a haber: una tabla de traducción es
 * un tercer artefacto que se desincroniza, que es exactamente la lección que
 * este repositorio ya aprendió con Zod y Pydantic. Los códigos van y vuelven
 * literales, y el texto legible viene de `permissions.description`, que ya
 * está poblada en la base.
 */

/** Un permiso tal como existe en la base. El texto viene con él. */
export interface PermisoDelCatalogo {
  codigo: string;
  modulo: string;
  descripcion: string;
}

/** Un permiso que la persona tiene, y de dónde le viene. */
export interface PermisoEfectivo {
  codigo: string;
  modulo: string;
  descripcion: string;
  /** `'rol'` si se lo da su rol, `'individual'` si se lo concedieron aparte. */
  origen: 'rol' | 'individual';
}

export interface PermisosDelUsuario {
  user_id: string;
  permisos: PermisoEfectivo[];
  /**
   * Códigos que el rol concede pero se le denegaron a esta persona.
   *
   * Vienen aparte porque una denegación **no aparece** en la lista de lo que
   * puede hacer, y sin verla nadie entiende por qué el rol no alcanza.
   */
  denegados: string[];
}

/**
 * Los tres estados en los que puede estar un permiso para una persona.
 *
 * No son dos. Una casilla marcada/desmarcada no alcanza porque *desmarcado*
 * significa dos cosas distintas: "su rol no se lo da" (y basta con no tocar
 * nada) y "su rol se lo da y se lo quitamos a ella", que es una fila explícita
 * en `user_permissions`. Sin distinguirlas, quitar el permiso de alguien y
 * dejar el default del rol se ven igual en pantalla.
 */
export type EstadoDePermiso = 'del-rol' | 'concedido' | 'denegado' | 'sin-permiso';

export function estadoDe(
  codigo: string,
  permisos: PermisosDelUsuario | null,
): EstadoDePermiso {
  if (!permisos) return 'sin-permiso';
  if (permisos.denegados.includes(codigo)) return 'denegado';
  const efectivo = permisos.permisos.find((p) => p.codigo === codigo);
  if (!efectivo) return 'sin-permiso';
  return efectivo.origen === 'individual' ? 'concedido' : 'del-rol';
}

/** Agrupa por módulo conservando el orden en que llegó desde la API. */
export function porModulo(
  catalogo: PermisoDelCatalogo[],
): { modulo: string; permisos: PermisoDelCatalogo[] }[] {
  const grupos: { modulo: string; permisos: PermisoDelCatalogo[] }[] = [];
  for (const permiso of catalogo) {
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.modulo === permiso.modulo) ultimo.permisos.push(permiso);
    else grupos.push({ modulo: permiso.modulo, permisos: [permiso] });
  }
  return grupos;
}

/**
 * Convierte `document.approve` en «Document approve» solo si hace falta.
 *
 * La descripción de la base es lo que se muestra; esto es el respaldo para una
 * fila que llegara sin ella. **No es un catálogo de nombres**: si empezara a
 * usarse de verdad, sería la segunda lista naciendo otra vez, y por eso el
 * backend tiene una prueba que falla si alguna fila llega sin descripción.
 */
export function nombreDeRespaldo(codigo: string): string {
  const legible = codigo.replace(/[._]/g, ' ');
  return legible.charAt(0).toUpperCase() + legible.slice(1);
}

export function cargarCatalogo(tenantId: string) {
  return api.get<PermisoDelCatalogo[]>('/permissions/', { tenantId });
}

export function cargarPermisosDe(userId: string, tenantId: string) {
  return api.get<PermisosDelUsuario>(`/users/${userId}/permissions`, { tenantId });
}

/**
 * Concede o deniega un permiso por encima del rol.
 *
 * `motivo` es obligatorio y el backend exige 3 caracteres: un permiso suelto
 * sin justificación es indistinguible de un error de configuración cuando
 * alguien lo audita seis meses después.
 */
export function fijarPermiso(
  userId: string,
  codigo: string,
  granted: boolean,
  motivo: string,
  tenantId: string,
) {
  return api.put<PermisosDelUsuario>(
    `/users/${userId}/permissions/${encodeURIComponent(codigo)}`,
    { codigo, granted, reason: motivo },
    { tenantId },
  );
}

/** Quita la excepción individual y devuelve a la persona a lo que da su rol. */
export function quitarExcepcion(userId: string, codigo: string, tenantId: string) {
  return api.delete<PermisosDelUsuario>(
    `/users/${userId}/permissions/${encodeURIComponent(codigo)}`,
    { tenantId },
  );
}
