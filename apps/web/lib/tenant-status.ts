import type { ModuloPlataforma } from '@ambienta/shared';

/**
 * `tenantSemaforo` se eliminó: mapeaba el estado administrativo de la cuenta
 * (activo/suspendido) al semáforo de cumplimiento ambiental, así que una
 * empresa suspendida por impago aparecía como "No cumple" — afirmando algo
 * falso sobre su situación regulatoria. Ahora se usa el átomo `AccountBadge`,
 * que es de otro eje y no se puede confundir con el semáforo.
 */

export const MODULO_LABEL: Record<ModuloPlataforma, string> = {
  'matriz-legal': 'Matriz Legal',
  obligaciones: 'Obligaciones',
  calendario: 'Calendario / Gantt',
  auditorias: 'Auditorías',
  'no-conformidades': 'No Conformidades',
  'catalogo-normativo': 'Catálogo Normativo',
  gestores: 'Gestores',
  reportes: 'Reportes',
  notificaciones: 'Notificaciones',
  'usuarios-roles': 'Usuarios y Roles',
  chatbot: 'Chatbot',
};
