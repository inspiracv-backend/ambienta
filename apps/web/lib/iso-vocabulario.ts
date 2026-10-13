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

/** `environmental_aspects.operating_condition`. */
export const CONDICION_OPERACION: Record<string, string> = {
  normal: 'Normal',
  anormal: 'Anormal',
  emergencia: 'Emergencia',
};

/**
 * `environmental_aspects.impact_type`, que es **texto libre** en la base: la
 * mayoria llega ya legible. Esto solo traduce los valores en clave que puedan
 * quedar de los datos de ejemplo; lo demas se muestra tal cual (`etiqueta`).
 *
 * Vivia dentro de la tabla de aspectos y paso aca el 21-sep, cuando la matriz
 * se empezo a exportar: con dos copias, la pantalla y el documento dirian
 * cosas distintas del mismo aspecto.
 */
export const TIPO_IMPACTO: Record<string, string> = {
  emision_atmosferica: 'Emisión atmosférica',
  vertido_agua: 'Vertido al agua',
  residuo_solido: 'Residuo sólido',
  residuo_peligroso: 'Residuo peligroso',
  consumo_agua: 'Consumo de agua',
  consumo_energia: 'Consumo de energía',
  ruido: 'Ruido',
  contaminacion_suelo: 'Contaminación de suelo',
  biodiversidad: 'Biodiversidad',
  gases_efecto_invernadero: 'GEI',
  otro: 'Otro',
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
