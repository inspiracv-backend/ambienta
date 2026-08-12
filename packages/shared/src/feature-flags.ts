/**
 * Feature flags del sistema.
 *
 * Existen para poder mostrar trabajo en curso sin comprometerse con él: una
 * rama obliga a elegir entre tener el trabajo o tener el sistema estable,
 * mientras que una flag permite enseñar la cadena de matrices a un cliente el
 * martes y apagarla el miércoles sin tocar código.
 *
 * Se leen de variables `NEXT_PUBLIC_*` porque el frontend las necesita en el
 * navegador. Next las reemplaza en tiempo de build, así que cambiar una exige
 * reconstruir, no solo reiniciar.
 */

/** Convierte el string de una variable de entorno en booleano. */
function flagActiva(valor: string | undefined, porDefecto: boolean): boolean {
  if (valor === undefined || valor === '') return porDefecto;
  return valor !== 'false' && valor !== '0';
}

export interface FeatureFlags {
  /**
   * Cadena de matrices de ISO 14001: aspectos e impactos (§6.1.2), riesgos y
   * oportunidades (§6.1.1), equipos regulados y los campos nuevos de la matriz
   * legal (§6.1.3, §9.1.2).
   *
   * Encendida por defecto: el objetivo de la propuesta
   * `matrices-ambientales-iso-14001` es evaluar la cadena, y con la flag
   * apagada no habría nada que evaluar. Se apaga con
   * `NEXT_PUBLIC_FF_MATRICES_ISO=false`.
   *
   * Con la flag apagada el sistema se comporta como antes del cambio: los
   * campos nuevos de `LegalNorm` son opcionales, así que la matriz actual
   * valida igual y nada del código existente depende de las entidades nuevas.
   */
  matricesIso: boolean;

  /**
   * Registro de Mejora con sus cinco tipos y sus cinco orígenes de detección,
   * en vez del formulario actual que asume que todo es no conformidad.
   *
   * Propuesta `hallazgos-auditoria-no-conformidades`. Se apaga con
   * `NEXT_PUBLIC_FF_REGISTRO_MEJORA=false`, y el formulario vuelve al de
   * hallazgo simple con criticidad alta/media/baja.
   */
  registroMejora: boolean;
}

export const FEATURE_FLAGS: FeatureFlags = {
  matricesIso: flagActiva(process.env.NEXT_PUBLIC_FF_MATRICES_ISO, true),
  registroMejora: flagActiva(process.env.NEXT_PUBLIC_FF_REGISTRO_MEJORA, true),
};

/** Azúcar sintáctico para leer una flag por nombre. */
export function flagHabilitada(flag: keyof FeatureFlags): boolean {
  return FEATURE_FLAGS[flag];
}
