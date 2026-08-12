import { z } from 'zod';

/**
 * Audit log transversal — RF-32, RNF-08 y RNF-25.
 *
 * El requisito no es "guardar cambios" sino poder responder, para cualquier
 * dato del sistema: **quién** lo cambió, **cuándo**, **qué** cambió, **por qué**
 * y **quién lo aprobó**. Es un requisito legal, no de conveniencia: ante una
 * fiscalización de la SMA, una discrepancia sin trazabilidad (por ejemplo,
 * kilogramos declarados distintos de los retirados) puede constituir
 * infracción, y la defensa de la empresa es justamente este registro.
 *
 * Por eso el modelo es único y genérico en vez de un historial por entidad:
 * un log por módulo obliga a reconstruir a mano la secuencia de hechos cuando
 * la pregunta cruza entidades ("¿qué pasó con esta planta en marzo?"), que es
 * exactamente la forma que toma una auditoría real.
 *
 * ⚠️ **Inmutabilidad (RNF-08): es una garantía del backend, no del frontend.**
 * En esta iteración el log vive en memoria y por tanto no es inmutable ni
 * persistente. La implementación real debe ser una tabla append-only sin
 * permisos de UPDATE ni DELETE para el rol de aplicación, con RLS por
 * `tenant_id`. Ver la propuesta OpenSpec `sistema-actores-roles-rbac`.
 */

/** Entidades del sistema que registran historial. */
export const EntidadAuditableSchema = z.enum([
  'ticket_soporte',
  'obligacion',
  'tarea',
  'norma',
  'articulo',
  'no_conformidad',
  'auditoria',
  'plan_accion',
  'usuario',
  'tenant',
  'sub_tenant',
  'contrato',
  'departamento',
  'planta',
]);
export type EntidadAuditable = z.infer<typeof EntidadAuditableSchema>;

/**
 * Acciones genéricas. Se mantienen pocas y transversales a propósito: si cada
 * módulo inventa sus propios verbos, la vista consolidada deja de poder
 * filtrar por tipo de acción.
 */
export const AccionAuditableSchema = z.enum([
  'creado',
  'actualizado',
  'estado_cambiado',
  'evaluado',
  'asignado',
  'cerrado',
  'reabierto',
  'suspendido',
  'reactivado',
  'eliminado',
  'exportado',
  'comentado',
]);
export type AccionAuditable = z.infer<typeof AccionAuditableSchema>;

/**
 * Un campo que cambió. `antes`/`despues` se guardan ya formateados para
 * lectura humana: el valor crudo (un id, un booleano) no le dice nada a quien
 * audita, y resolverlo al momento de mostrar sería imposible si la entidad
 * referenciada se borró después.
 */
export const CambioCampoSchema = z.object({
  campo: z.string(),
  antes: z.string().nullable(),
  despues: z.string().nullable(),
});
export type CambioCampo = z.infer<typeof CambioCampoSchema>;

export const AuditLogEntrySchema = z.object({
  id: z.string(),
  /** `null` para eventos de plataforma (acciones del Superadmin sobre tenants). */
  tenantId: z.string().nullable(),
  entidadTipo: EntidadAuditableSchema,
  entidadId: z.string(),
  /**
   * Nombre legible de la entidad **en el momento del evento**. Es una foto, no
   * una referencia: si una norma se renombra o un usuario se elimina, el
   * historial debe seguir diciendo sobre qué se actuó entonces.
   */
  entidadLabel: z.string(),
  accion: AccionAuditableSchema,
  /** Frase corta y legible: "Cambió el estado de abierto a en progreso". */
  resumen: z.string(),
  cambios: z.array(CambioCampoSchema).default([]),
  actorId: z.string(),
  /** Igual que `entidadLabel`: foto del nombre al momento del evento. */
  actorNombre: z.string(),
  actorRol: z.string(),
  fecha: z.string(),
  /** RF-32 "por qué". Obligatorio en las acciones que lo exigen (ej. corrección de logs, RF-83). */
  motivo: z.string().optional(),
  /** RF-32 "quién aprobó" — solo en flujos con aprobación, como el cierre de una NC (RF-49). */
  aprobadoPorId: z.string().optional(),
  aprobadoPorNombre: z.string().optional(),
});
export type AuditLogEntry = z.infer<typeof AuditLogEntrySchema>;

export const ENTIDAD_LABEL: Record<EntidadAuditable, string> = {
  ticket_soporte: 'Ticket de soporte',
  obligacion: 'Obligación',
  tarea: 'Tarea',
  norma: 'Norma',
  articulo: 'Artículo',
  no_conformidad: 'No conformidad',
  auditoria: 'Auditoría',
  plan_accion: 'Plan de acción',
  usuario: 'Usuario',
  tenant: 'Empresa',
  sub_tenant: 'Cliente (sub-tenant)',
  contrato: 'Contrato',
  departamento: 'Departamento',
  planta: 'Planta',
};

export const ACCION_LABEL: Record<AccionAuditable, string> = {
  creado: 'Creado',
  actualizado: 'Actualizado',
  estado_cambiado: 'Cambio de estado',
  evaluado: 'Evaluado',
  asignado: 'Asignado',
  cerrado: 'Cerrado',
  reabierto: 'Reabierto',
  suspendido: 'Suspendido',
  reactivado: 'Reactivado',
  eliminado: 'Eliminado',
  exportado: 'Exportado',
  comentado: 'Comentario',
};
