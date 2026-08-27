/**
 * Fechas legibles, sin perder un día por el camino.
 *
 * ## El error que este módulo existe para evitar
 *
 * `new Date('2026-08-27')` **no** es el 27 de agosto a las 00:00 en Chile: la
 * norma dice que una cadena de sólo fecha se interpreta como **medianoche
 * UTC**. Al mostrarla con `toLocaleDateString`, el navegador la traduce a la
 * hora local —UTC−4— y sale el **26**.
 *
 * Se detectó en el navegador, no en las pruebas: la API guardaba `2026-08-27`
 * en `valid_from` y la pantalla decía "Rige desde 26 ago 2026". En un sistema
 * de cumplimiento eso no es un detalle de formato — `valid_from` es la fecha
 * desde la que un procedimiento rige, y contestarla con un día de menos es
 * exactamente lo que un auditor va a mirar.
 *
 * Afecta a **todo huso al oeste de Greenwich**, que incluye a toda América. Al
 * este pasa lo contrario y no se nota, que es peor: el error queda esperando a
 * que alguien abra la aplicación desde otro lado.
 *
 * ## La distinción que hace este módulo
 *
 * - **Fecha sola** (`2026-08-27`): se formatea con sus propios números, sin
 *   pasar por `Date`. Un día calendario no tiene huso.
 * - **Marca de tiempo** (`2026-08-27T18:59:16Z`): sí lleva instante, y ahí
 *   convertir a la hora local es lo correcto — la hora en que alguien subió un
 *   archivo se lee en la hora de quien mira.
 */

const SOLO_FECHA = /^\d{4}-\d{2}-\d{2}$/;

const MESES = [
  'ene',
  'feb',
  'mar',
  'abr',
  'may',
  'jun',
  'jul',
  'ago',
  'sep',
  'oct',
  'nov',
  'dic',
];

/** `2026-08-27` → `27 ago 2026`. Sin `Date`, sin husos, sin perder un día. */
export function fechaCalendario(iso: string): string {
  const [anio, mes, dia] = iso.split('-');
  const nombreMes = MESES[Number(mes) - 1];
  if (!nombreMes) return iso;
  return `${dia} ${nombreMes} ${anio}`;
}

/** Una marca de tiempo en la hora de quien mira. */
export function fechaDeInstante(iso: string): string {
  return new Date(iso).toLocaleDateString('es-CL', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Formatea lo que venga, eligiendo según la forma del dato.
 *
 * Elegir por la forma y no por el nombre del campo es lo que hace que esto no
 * se pueda usar mal: quien escriba `fecha(rev.rigeDesde)` acierta sin tener que
 * acordarse de qué columna es fecha y cuál es instante.
 */
export function fecha(iso: string | null | undefined): string {
  if (!iso) return '—';
  return SOLO_FECHA.test(iso) ? fechaCalendario(iso) : fechaDeInstante(iso);
}
