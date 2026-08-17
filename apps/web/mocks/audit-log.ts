import type { AuditLogEntry } from '@ambienta/shared';

function hace(dias: number, horas = 0): string {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  d.setHours(d.getHours() - horas);
  return d.toISOString();
}

/**
 * Historial preexistente (RF-32, RNF-08).
 *
 * Sin semilla, cada pantalla de historial arrancaría vacía y no se podría
 * evaluar el diseño: el caso interesante de un audit log no es "no hay nada"
 * sino leer una secuencia de hechos encadenados. Estos eventos reconstruyen
 * la vida de entidades que ya existen en los demás mocks: el ticket TCK-1042
 * y la no conformidad NC-1 (la discrepancia de kilogramos declarados vs.
 * retirados, que es justo el escenario donde la trazabilidad se vuelve
 * defensa legal ante la SMA).
 */
export const mockAuditLog: AuditLogEntry[] = [
  // ── Ticket de soporte TCK-1042 ────────────────────────────────────────────
  {
    id: 'audit-seed-1',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    entidadTipo: 'ticket_soporte',
    entidadId: 'ticket-1',
    entidadLabel: 'TCK-1042 — No puedo visualizar el certificado de un artículo',
    accion: 'creado',
    resumen: 'Creó el ticket desde el formulario de solicitudes',
    cambios: [],
    actorId: 'user-interno',
    actorNombre: 'Camila Rojas',
    actorRol: 'usuario_interno',
    fecha: hace(4),
  },
  {
    id: 'audit-seed-2',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    entidadTipo: 'ticket_soporte',
    entidadId: 'ticket-1',
    entidadLabel: 'TCK-1042 — No puedo visualizar el certificado de un artículo',
    accion: 'estado_cambiado',
    resumen: 'Tomó el ticket y lo pasó a en progreso',
    cambios: [{ campo: 'Estado', antes: 'Abierto', despues: 'En progreso' }],
    actorId: 'user-superadmin',
    actorNombre: 'Javiera Soto',
    actorRol: 'superadmin',
    fecha: hace(3, 5),
  },
  {
    id: 'audit-seed-3',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    entidadTipo: 'ticket_soporte',
    entidadId: 'ticket-1',
    entidadLabel: 'TCK-1042 — No puedo visualizar el certificado de un artículo',
    accion: 'comentado',
    resumen: 'Registró una nota interna de diagnóstico',
    cambios: [],
    actorId: 'user-superadmin',
    actorNombre: 'Javiera Soto',
    actorRol: 'superadmin',
    fecha: hace(2),
    motivo: 'El enlace de evidencia apunta a un archivo de Drive sin permisos de lectura para el tenant.',
  },

  // ── No conformidad NC-1 ───────────────────────────────────────────────────
  {
    id: 'audit-seed-4',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    entidadTipo: 'no_conformidad',
    entidadId: 'nc-1',
    entidadLabel: 'NC-001 — Discrepancia entre kilogramos declarados y retirados',
    accion: 'creado',
    resumen: 'Registró el hallazgo durante la auditoría interna de Rancagua',
    cambios: [],
    actorId: 'user-especialista',
    actorNombre: 'Diego Muñoz',
    actorRol: 'usuario_interno',
    fecha: hace(12),
  },
  {
    id: 'audit-seed-5',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    entidadTipo: 'no_conformidad',
    entidadId: 'nc-1',
    entidadLabel: 'NC-001 — Discrepancia entre kilogramos declarados y retirados',
    accion: 'actualizado',
    resumen: 'Completó el análisis de causa raíz (5 ¿Por qué?)',
    cambios: [
      { campo: 'Criticidad', antes: 'Media', despues: 'Alta' },
      { campo: 'Causa raíz', antes: null, despues: 'La balanza del patio no estaba calibrada desde 2025' },
    ],
    actorId: 'user-especialista',
    actorNombre: 'Diego Muñoz',
    actorRol: 'usuario_interno',
    fecha: hace(9),
    motivo: 'La diferencia supera el 5% permitido y puede constituir infracción ante la SMA.',
  },

  // ── Plataforma (sin tenant) ───────────────────────────────────────────────
  {
    id: 'audit-seed-6',
    tenantId: null,
    entidadTipo: 'tenant',
    entidadId: 'a0000000-0000-0000-0000-000000000002',
    entidadLabel: 'Veolia Ambiental Chile',
    accion: 'actualizado',
    resumen: 'Amplió el límite de usuarios contratado',
    cambios: [{ campo: 'Límite de usuarios', antes: '5', despues: '10' }],
    actorId: 'user-superadmin',
    actorNombre: 'Javiera Soto',
    actorRol: 'superadmin',
    fecha: hace(20),
    motivo: 'Ampliación solicitada por el cliente al incorporar dos sub-tenants nuevos.',
  },
];
