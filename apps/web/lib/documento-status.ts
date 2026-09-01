import { ETIQUETA_ESTADO_REVISION, type EstadoRevision } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms';

/**
 * El estado de una revisión, dicho con el semáforo de la plataforma (H4).
 *
 * Mismo criterio que `notification-status.ts` y que Auditorías: **nunca un
 * valor nuevo en `StatusBadge`**, siempre ícono + color + texto. Lo que se
 * pasa aparte es la palabra, porque "Borrador" no es "Pendiente de evaluar".
 *
 * Las dos decisiones de color que no son obvias:
 *
 * - **`aprobado` va en ámbar, no en verde.** Aprobada pero sin entrar en
 *   vigencia significa que **todavía rige la anterior**, y pintarla de verde
 *   invitaría a usarla como evidencia. `SIRVE_COMO_EVIDENCIA` en la API es
 *   sólo `vigente`, y el color tiene que decir lo mismo.
 * - **`obsoleto` va en gris, no en rojo.** Retirar un documento es el final
 *   normal de su vida, no un incumplimiento. En rojo, una carpeta con diez
 *   años de historial se vería como un desastre.
 */
export function estadoRevisionSemaforo(estado: EstadoRevision): SemaforoStatus {
  switch (estado) {
    case 'vigente':
      return 'vigente';
    case 'aprobado':
      return 'parcial';
    case 'en_revision':
      return 'por_vencer';
    case 'obsoleto':
      return 'na';
    case 'borrador':
    default:
      return 'pendiente';
  }
}

export function etiquetaEstadoRevision(estado: EstadoRevision): string {
  return ETIQUETA_ESTADO_REVISION[estado] ?? estado;
}

/**
 * El estado del documento entero (`documents.status`), que no es el mismo
 * conjunto que el de la revisión.
 *
 * `db/18` lo dejó en `borrador | en_revision | vigente | obsoleto` — sin
 * `aprobado`, porque un documento no está "aprobado": lo está una revisión
 * suya. Se mapea aparte para que ese desfase quede explícito en vez de
 * resolverse con un `as` que oculte que son dos conjuntos distintos.
 */
export function estadoDocumentoSemaforo(estado: string): SemaforoStatus {
  switch (estado) {
    case 'vigente':
      return 'vigente';
    case 'en_revision':
      return 'por_vencer';
    case 'obsoleto':
      return 'na';
    default:
      return 'pendiente';
  }
}

export const ETIQUETA_ESTADO_DOCUMENTO: Record<string, string> = {
  borrador: 'Sin nada vigente',
  en_revision: 'En revisión',
  vigente: 'Vigente',
  obsoleto: 'Obsoleto',
};

export function etiquetaEstadoDocumento(estado: string): string {
  return ETIQUETA_ESTADO_DOCUMENTO[estado] ?? estado;
}
