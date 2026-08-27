/**
 * Semáforo único de la plataforma (H2 + H4): siempre ícono + color + texto,
 * nunca solo color. Reutilizado por Dashboard, Matriz Legal, Obligaciones,
 * Calendario — un solo átomo para todas las pantallas.
 */
export type SemaforoStatus =
  | 'cumple'
  | 'parcial'
  | 'no_cumple'
  | 'na'
  | 'pendiente'
  | 'vigente'
  | 'por_vencer'
  | 'vencida'
  | 'sin_evidencia';

export interface StatusBadgeProps {
  status: SemaforoStatus;
  className?: string;
  /**
   * Texto propio, manteniendo el ícono y el color del semáforo.
   *
   * Existe para el control documental: sus estados —borrador, en revisión,
   * aprobada, vigente, obsoleta— **significan** lo mismo que el semáforo
   * (neutro / atención / bien), pero se llaman distinto. Sin esto, una
   * revisión en borrador saldría rotulada "Pendiente de evaluar", que habla de
   * otra cosa.
   *
   * La alternativa era agregar cinco valores nuevos a `SemaforoStatus`, y eso
   * está descartado a propósito: el semáforo es uno solo para toda la
   * plataforma (H4), y cada valor nuevo lo diluye hasta que deja de leerse de
   * un vistazo. Lo que cambia acá es la palabra, no el código de color.
   */
  label?: string;
}
