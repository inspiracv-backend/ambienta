import { z } from 'zod';

export const TipoDocumentoSchema = z.enum([
  'NCh',
  'Ley',
  'Decreto',
  'DFL',
  'Constitucion',
  'Circular',
  'Resolucion',
  'Ordenanza',
  'Autorizacion',
  'Guia',
]);
export type TipoDocumento = z.infer<typeof TipoDocumentoSchema>;

export const RespuestaCumplimientoSchema = z.enum(['SI', 'NO', 'NA', 'N_E']);
export type RespuestaCumplimiento = z.infer<typeof RespuestaCumplimientoSchema>;

export const ArticuloSchema = z.object({
  id: z.string(),
  normId: z.string(),
  numero: z.string(),
  descripcion: z.string(),
  respuesta: RespuestaCumplimientoSchema,
  formaCumplimiento: z.string().optional(),
  responsableId: z.string().optional(),
  evidenciaUrl: z.string().optional(),
  incluidoEnCalculo: z.boolean().default(true),
});
export type Articulo = z.infer<typeof ArticuloSchema>;

/** Estado de sincronización del agente BCN (RF-45) — solo aplica a normas `fuente: 'BCN'`. */
export const SincronizacionSchema = z.object({
  estado: z.enum(['sincronizado', 'desactualizado', 'error']),
  fecha: z.string(),
});
export type Sincronizacion = z.infer<typeof SincronizacionSchema>;

/**
 * Matriz Legal: capa macro/estructural, separada de Obligation (capa concurrente)
 * — relación bidireccional (RF-14). El % de cumplimiento se deriva de `articulos`
 * (ver apps/web/lib/legal-matrix.ts), no se guarda como campo independiente para
 * evitar datos duplicados/desincronizados.
 */
export const LegalNormSchema = z.object({
  id: z.string(),
  tenantId: z.string().nullable(),
  plantIds: z.array(z.string()),
  tipoDocumento: TipoDocumentoSchema,
  nombre: z.string(),
  fuente: z.enum(['BCN', 'ISO', 'RCA']),
  fuenteUrl: z.string().optional(),
  responsableId: z.string().optional(),
  articulos: z.array(ArticuloSchema),
  sincronizacion: SincronizacionSchema.optional(),
});
export type LegalNorm = z.infer<typeof LegalNormSchema>;
