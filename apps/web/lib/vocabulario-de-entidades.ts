import type { EntidadAuditable } from '@ambienta/shared';

/**
 * Del nombre en español que usa la aplicación al que entiende la API.
 *
 * ## Por qué hace falta esto
 *
 * Hay **tres** nombres para la misma cosa, y el tercero es este:
 *
 * | dónde | una obligación se llama |
 * |---|---|
 * | `audit_log.entity_type` | `obligations` — el nombre de la **tabla** |
 * | `comments`, `entity_documents`, `/historial` | `obligation` — el de **dominio** |
 * | `packages/shared` (`EntidadAuditable`) | `obligacion` — en **español** |
 *
 * Manda el de dominio, que es el que la API valida. El servidor traduce el de
 * tabla por su cuenta —derivándolo del modelo— así que acá sólo falta el
 * puente desde el español.
 *
 * **No se renombró el enum español.** Está en `packages/shared` y lo usan las
 * cinco pantallas de detalle, el filtro del registro de auditoría y los
 * eventos que se registran en el navegador; cambiarlo sería tocar todo eso
 * para ahorrar este archivo.
 */
export const TIPO_EN_LA_API: Partial<Record<EntidadAuditable, string>> = {
  obligacion: 'obligation',
  tarea: 'task',
  norma: 'legal_norm',
  articulo: 'article_compliance',
  no_conformidad: 'nonconformity',
  auditoria: 'audit',
  plan_accion: 'action_plan',
  contrato: 'contract',
};

/**
 * Las entidades cuya historia **no está en la API**, con el motivo.
 *
 * Que estén acá no es un pendiente disimulado: son cosas que el mapa de
 * anclajes del servidor no cubre, y para ellas la línea de tiempo sigue
 * mostrando sólo lo de la sesión — que es lo que hacía antes de este cambio,
 * ni mejor ni peor.
 *
 * La prueba de este archivo exige que **cada** `EntidadAuditable` esté acá o
 * arriba. Sin eso, agregar un tipo nuevo al enum lo dejaría sin historia y sin
 * que nada avisara: la pantalla diría «no pasó nada» sobre un registro con
 * actividad.
 */
export const SIN_HISTORIA_EN_LA_API: Partial<Record<EntidadAuditable, string>> = {
  ticket_soporte:
    'los mensajes del ticket son su propia conversación (`support_ticket_messages`), con reglas de visibilidad distintas: llevan `is_internal` para lo que el cliente no ve',
  usuario:
    'una persona no es un registro de negocio comentable ni adjuntable. Su actividad se lee en el registro de auditoría global, filtrando por actor',
  tenant:
    'la empresa es el contenedor, no un registro dentro de ella. Su historia es la de la plataforma, no la de una ficha',
  sub_tenant:
    'un sub-tenant es una empresa, no una ficha dentro de una: su historia es la de esa cuenta, que se lee entrando a ella. Lo que sí tiene historia propia es el **contrato** que la vincula con su gestor, y ese sí está mapeado',
  departamento:
    'parte del perfil de la empresa; su historia se lee en la ficha de la empresa',
  planta:
    'lo mismo que departamento. Si algún día se comenta una planta, entra en el mapa de anclajes del servidor y después acá',
};

/** El tipo que entiende la API, o `null` si esa entidad no tiene historia allá. */
export function tipoEnLaApi(entidad: EntidadAuditable): string | null {
  return TIPO_EN_LA_API[entidad] ?? null;
}
