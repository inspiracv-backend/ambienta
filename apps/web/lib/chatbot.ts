import { ApiError, api, codigoDeError, mensajeDeError } from './api-client';

/**
 * El asistente, visto desde el navegador (RF-59 a RF-63).
 *
 * **Se le pregunta a la API, no al AI Service.** Ese servicio no se publica a
 * internet: vive en la red interna del compose y sólo la API lo alcanza. El
 * navegador manda la pregunta a `/support/chatbot/consulta`, que autoriza con
 * el token de quien pregunta y reenvía.
 *
 * Y por eso este archivo no sabe nada del AI Service salvo la forma de su
 * respuesta: ni su dirección, ni una clave, ni un modo de autenticarse.
 */

/**
 * Una referencia verificable: de dónde sale lo que el asistente afirmó.
 *
 * La forma es la del AI Service, que es quien versiona el contrato. Se declara
 * entera y no como `unknown` porque la pantalla tiene que poder enlazar a la
 * norma; los campos que ellos agreguen llegan igual —la fachada no los filtra—
 * y aparecerán acá cuando se usen.
 */
export interface CitaDelAsistente {
  norma: string;
  articulo: string | null;
  texto: string;
  ruta: string;
  norm_id: string;
  article_id: string | null;
  norm_version_id: string | null;
  official_url: string | null;
  origen: 'catalogo' | 'normativa_propia' | 'documento';
}

export interface RespuestaDelAsistente {
  /** La conversación. **La abre el AI Service si no se mandó una**, y hay que guardarla. */
  conversation_id: string | null;
  respuesta: string;
  /**
   * **Viene del servicio, no se deduce del texto.**
   *
   * Una respuesta fundamentada y un «no tengo información suficiente» se
   * muestran distinto, y adivinarlo leyendo el texto es como se termina
   * presentando una abstención como si fuera un hecho comprobado.
   */
  se_abstuvo: boolean;
  citas: CitaDelAsistente[];
  /** Si el turno quedó guardado en la conversación. En modo desarrollo, `false`. */
  guardado: boolean;
}

/** El entorno no tiene `AI_SERVICE_URL`: la capacidad no está, no se cayó. */
export const SIN_CONFIGURAR = 'ai_service_sin_configurar';
/** El AI Service no contestó o contestó mal. Reintentar tiene sentido. */
export const NO_RESPONDE = 'ai_service_no_responde';

export interface Consulta {
  pregunta: string;
  /** El id que devolvió el turno anterior, o nada en el primero. */
  conversacionId?: string | null;
  /** `AAAA-MM-DD` para preguntar por el texto legal vigente a esa fecha. */
  fecha?: string;
  /**
   * La empresa de la sesión, **para el modo sin Clerk**.
   *
   * Con Clerk la API ignora `X-Tenant-Id` y lee el token; sin Clerk no hay
   * token y la cabecera es lo único que dice de qué empresa se pregunta —
   * sin ella responde 401, que es lo que pasaba acá hasta que se probó la
   * pantalla contra la API de verdad. Va **fuera del cuerpo**: es una
   * cabecera de desarrollo, no un parámetro con el que se elige empresa.
   */
  tenantId?: string;
}

/**
 * Pregunta y espera la respuesta completa.
 *
 * Los opcionales **se omiten** en vez de mandarse en null: para la API es lo
 * mismo, y para quien lee un log no.
 */
export function consultarAlAsistente({
  pregunta,
  conversacionId,
  fecha,
  tenantId,
}: Consulta): Promise<RespuestaDelAsistente> {
  const cuerpo: Record<string, unknown> = { pregunta };
  if (conversacionId) cuerpo.conversation_id = conversacionId;
  if (fecha) cuerpo.fecha = fecha;
  return api.post<RespuestaDelAsistente>('/support/chatbot/consulta', cuerpo, { tenantId });
}

/**
 * Qué mostrarle a la persona cuando la consulta falla.
 *
 * **"No está configurado" y "no respondió" no son lo mismo**, y la diferencia
 * es lo único que decide si tiene sentido volver a intentar. Mostrar un error
 * genérico para los dos deja a alguien reintentando contra un entorno que
 * todavía no tiene el servicio.
 */
export function mensajeDeFalla(error: unknown): string {
  if (esConversacionPerdida(error)) {
    return 'Esa conversación ya no existe. Vuelve a preguntar y se abrirá una nueva.';
  }
  switch (codigoDeError(error)) {
    case SIN_CONFIGURAR:
      return 'El asistente todavía no está disponible en este entorno.';
    case NO_RESPONDE:
      return 'El asistente no respondió. Vuelve a intentarlo en un momento.';
    default:
      return mensajeDeError(error);
  }
}

/**
 * La conversación que se venía arrastrando ya no está.
 *
 * **Y hay que soltarla, no sólo avisar.** La API valida que la conversación
 * sea de esta empresa antes de reenviar; si se retiró, o nunca existió, cada
 * pregunta siguiente viaja con el mismo id muerto y vuelve a fallar: el chat
 * queda roto hasta recargar la página, y nada en la pantalla dice por qué.
 * Visto en el navegador, no deducido.
 */
export function esConversacionPerdida(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

/** Si reintentar puede servir. Un servicio sin configurar no se arregla insistiendo. */
export function valeLaPenaReintentar(error: unknown): boolean {
  return codigoDeError(error) !== SIN_CONFIGURAR;
}
