import { api } from './api-client';

/**
 * A qué instalaciones y departamentos está acotada la persona de la sesión.
 *
 * ## Por qué esto existe
 *
 * Siete pantallas —auditorías, calendario, dashboard, matriz legal, no
 * conformidades, obligaciones y reportes— acotan lo que muestran con
 * `user.plantIds.length > 0`. Y `users-store` armaba **`plantIds: []` fijo**
 * para todo el mundo, así que esa condición nunca era cierta: **el
 * acotamiento por planta no se aplicaba en ninguna de las siete**.
 *
 * No era un endpoint que faltara. `GET /me` devuelve `instalaciones` desde el
 * 20-ago, calculado por `services/permisos.py::alcance_del_usuario` sobre los
 * roles vigentes. Lo que faltaba era pedirlo.
 *
 * ## La regla que hay que respetar
 *
 * **Una lista vacía significa «sin acotar», no «ninguna».** Es la diferencia
 * entre un encargado de toda la empresa y uno sin acceso a nada, y la API lo
 * dice explícito en el campo `acotado`. Invertirlo dejaría a los
 * administradores sin ver nada — que es el error que se comete al leer `[]`
 * como "cero plantas".
 *
 * Por eso `undefined` (todavía no se sabe) y `[]` (sin acotar) son valores
 * distintos y no se pueden colapsar: durante la carga, tratarlos igual haría
 * que alguien acotado a una planta viera todas por un instante.
 */
export interface AlcanceDeLaSesion {
  /**
   * Si el alcance está limitado. Lo dice la API en vez de deducirse de las
   * listas, para que nadie tenga que acordarse de la regla de arriba.
   */
  acotado: boolean;
  /** Vacío = sin acotar, ve todas las plantas. */
  instalaciones: string[];
  /** Vacío = sin acotar. */
  departamentos: string[];
}

interface RespuestaMe {
  acotado?: boolean;
  instalaciones?: string[];
  departamentos?: string[];
}

export async function cargarAlcance(tenantId: string): Promise<AlcanceDeLaSesion> {
  const me = await api.get<RespuestaMe>('/me', { tenantId });
  return {
    acotado: me.acotado ?? false,
    instalaciones: me.instalaciones ?? [],
    departamentos: me.departamentos ?? [],
  };
}
