import { z } from 'zod';

export const SistemaDeclaracionSchema = z.enum([
  'RETC',
  'Ley REP',
  'SINADER',
  'SIDREP',
  'DAE',
]);
export type SistemaDeclaracion = z.infer<typeof SistemaDeclaracionSchema>;

export const ObligationStatusSchema = z.enum([
  'vigente',
  'por_vencer',
  'vencida',
  'sin_evidencia',
]);
export type ObligationStatus = z.infer<typeof ObligationStatusSchema>;

export const ObligationTaskSchema = z.object({
  id: z.string(),
  obligationId: z.string(),
  titulo: z.string(),
  vencimiento: z.string(),
  responsableId: z.string(),
  estado: ObligationStatusSchema,
  evidenciaUrl: z.string().optional(),
});
export type ObligationTask = z.infer<typeof ObligationTaskSchema>;

/** Cada declaración periódica se modela como "megaproyecto" (RF-15). */
export const ObligationSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  plantId: z.string(),
  sistema: SistemaDeclaracionSchema,
  nombre: z.string(),
  periodo: z.string(),
  estado: ObligationStatusSchema,
  proximoVencimiento: z.string(),
  responsableId: z.string(),
  tasks: z.array(ObligationTaskSchema),
  /** Declaración de un cliente final de un tenant Gestor (RF-57, Sección I) — ausente para tenants no-Gestor. */
  subTenantId: z.string().optional(),
  /**
   * El artículo de la Matriz Legal del que nace esta obligación (RF-09, RF-14).
   *
   * Es el id de la **evaluación** (`article_compliance`), no el del artículo del
   * catálogo: el artículo es global y no diría de qué empresa ni de qué planta
   * es. Ausente en una obligación creada libremente, que es legítimo — RF-14
   * pide separarlas manteniendo la relación, no obligar a que exista.
   */
  articuloOrigenId: z.string().optional(),
  /** La norma de la que cuelga, para poder volver a ella desde la obligación. */
  normaOrigenId: z.string().optional(),
  /**
   * El comprobante que devolvió el portal del Estado (#114).
   *
   * Es la única prueba de que la declaración se presentó, y por eso la API no
   * deja aceptarla sin él. Ausente mientras nadie lo haya registrado.
   */
  folio: z.string().optional(),
  /** Por qué se devolvió la declaración a quien la preparó (RF-31). */
  motivoRechazo: z.string().optional(),
  /**
   * La dirección del portal ante el que se declara.
   *
   * Sale del catálogo `retc_systems` y no de una copia en la obligación: los
   * portales del Estado cambian de dirección, y copiada habría que corregirla
   * fila por fila.
   */
  sistemaUrl: z.string().optional(),
});
export type Obligation = z.infer<typeof ObligationSchema>;
