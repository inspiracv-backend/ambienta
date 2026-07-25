import type { ModuloPlataforma, Tenant } from '@ambienta/shared';
import type { SemaforoStatus } from '@/components/atoms';

export function tenantSemaforo(estado: Tenant['estado']): SemaforoStatus {
  return estado === 'activo' ? 'cumple' : 'no_cumple';
}

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
