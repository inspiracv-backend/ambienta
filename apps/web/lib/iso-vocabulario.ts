/**
 * Las etiquetas de las tres pantallas ISO, en el vocabulario **de la base**.
 *
 * ## Por qué acá y no en cada tabla
 *
 * Los valores viven en CHECK constraints de PostgreSQL. Repartir las
 * traducciones por los componentes hace que cada uno conozca un subconjunto, y
 * el día que la base admita uno nuevo aparece el valor crudo en pantalla —
 * `in_treatment` en vez de "En tratamiento"— sin que nada falle.
 *
 * ## Y por qué están en inglés
 *
 * Porque así los guarda la base. `packages/shared` los define en español
 * (`riesgo`, `identificado`, `aspecto_ambiental`), y esa divergencia es real:
 * el modelo está escrito dos veces y estas pantallas leían la versión de los
 * datos de ejemplo. Manda la base.
 */

/** `risks_opportunities.entry_type` */
export const TIPO_REGISTRO: Record<string, string> = {
  risk: 'Riesgo',
  opportunity: 'Oportunidad',
};

/** `risks_opportunities.status` */
export const ESTADO_REGISTRO: Record<string, string> = {
  identified: 'Identificado',
  in_treatment: 'En tratamiento',
  controlled: 'Controlado',
  closed: 'Cerrado',
};

/** `risks_opportunities.origin` */
export const ORIGEN_REGISTRO: Record<string, string> = {
  environmental_aspect: 'Aspecto ambiental',
  context: 'Contexto',
  climate_change: 'Cambio climático',
  compliance: 'Requisito legal',
  other: 'Otro',
};

/** `risks_opportunities.risk_level` */
export const NIVEL_RIESGO: Record<string, string> = {
  low: 'Bajo',
  medium: 'Medio',
  high: 'Alto',
  critical: 'Crítico',
};

/** `risks_opportunities.treatment` */
export const TRATAMIENTO: Record<string, string> = {
  mitigate: 'Mitigar',
  avoid: 'Evitar',
  transfer: 'Transferir',
  accept: 'Aceptar',
  exploit: 'Aprovechar',
};

/** `regulated_equipment.status` */
export const ESTADO_EQUIPO: Record<string, string> = {
  operational: 'Operativo',
  stopped: 'Detenido',
  decommissioned: 'Dado de baja',
};

/** `regulated_equipment.registration_authority` */
export const AUTORIDAD: Record<string, string> = {
  SEC: 'SEC',
  SISS: 'SISS',
  SEREMI_SALUD: 'SEREMI de Salud',
  DGA: 'DGA',
  SMA: 'SMA',
  OTRO: 'Otra',
};

/** `environmental_aspects.significance` (ver `db/21`). */
export const SIGNIFICANCIA: Record<string, string> = {
  significant: 'Significativo',
  not_significant: 'No significativo',
  pending: 'Sin evaluar',
};

/**
 * Traduce, y si no conoce el valor **lo muestra crudo** en vez de esconderlo.
 *
 * Un `—` o una cadena vacía haría que un valor nuevo de la base pasara
 * desapercibido; el valor crudo se ve feo, que es exactamente lo que hace que
 * alguien lo arregle.
 */
export function etiqueta(mapa: Record<string, string>, valor: string | null): string {
  if (!valor) return '—';
  return mapa[valor] ?? valor;
}

/** Las opciones de un desplegable, en el orden en que están declaradas. */
export function opciones(mapa: Record<string, string>) {
  return Object.entries(mapa).map(([value, label]) => ({ value, label }));
}
