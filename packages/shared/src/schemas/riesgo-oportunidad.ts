import { z } from 'zod';

/**
 * Matriz de riesgos y oportunidades — ISO 14001 §6.1.4.
 *
 * Hoy `riesgo` y `oportunidad` son dos valores de un desplegable en el registro
 * de mejoras. Eso trata un requisito de planificacion como si fuera un
 * incidente: §6.1.4 pide determinarlos **al planificar**, no cuando alguien los
 * reporta. Por eso son entidad propia.
 *
 * Un registro de mejora puede seguir originando una entrada aca
 * (`origen: 'registro_mejora'`), pero la matriz existe con independencia de que
 * alguien reporte algo. Esa es la diferencia entre planificar y reaccionar.
 */

export const TipoRiesgoOportunidadSchema = z.enum(['riesgo', 'oportunidad']);
export type TipoRiesgoOportunidad = z.infer<typeof TipoRiesgoOportunidadSchema>;

/**
 * De donde salio. §6.1.4 los deriva del contexto (§4.1) y de las necesidades de
 * las partes interesadas (§4.2); `cambio_climatico` es explicito porque la
 * edicion 2026 lo incorpora al contexto ambiental.
 */
export const OrigenRiesgoOportunidadSchema = z.enum([
  'aspecto_ambiental',
  'requisito_legal',
  'contexto',
  'parte_interesada',
  'auditoria',
  'cambio_climatico',
  'registro_mejora',
]);
export type OrigenRiesgoOportunidad = z.infer<typeof OrigenRiesgoOportunidadSchema>;

export const NivelRiesgoSchema = z.enum(['bajo', 'medio', 'alto', 'critico']);
export type NivelRiesgo = z.infer<typeof NivelRiesgoSchema>;

/**
 * Opciones de tratamiento. Las cuatro primeras aplican a riesgos; las dos
 * ultimas a oportunidades.
 */
export const TratamientoSchema = z.enum([
  'evitar',
  'mitigar',
  'transferir',
  'aceptar',
  'aprovechar',
  'descartar',
]);
export type Tratamiento = z.infer<typeof TratamientoSchema>;

export const EstadoRiesgoOportunidadSchema = z.enum([
  'identificado',
  'en_tratamiento',
  'controlado',
  'cerrado',
]);
export type EstadoRiesgoOportunidad = z.infer<typeof EstadoRiesgoOportunidadSchema>;

export const EvaluacionRiesgoSchema = z.object({
  probabilidad: z.number().int().min(1),
  consecuencia: z.number().int().min(1),
  nivel: NivelRiesgoSchema,
  /** Metodo del catalogo del tenant (matriz probabilidad x consecuencia). */
  metodoId: z.string(),
  fecha: z.string(),
});
export type EvaluacionRiesgo = z.infer<typeof EvaluacionRiesgoSchema>;

export const RiesgoOportunidadSchema = z
  .object({
    id: z.string(),
    tenantId: z.string(),
    plantId: z.string(),
    codigo: z.string(),

    tipo: TipoRiesgoOportunidadSchema,
    origen: OrigenRiesgoOportunidadSchema,
    /** Id de la entidad de origen cuando `origen` apunta a una. */
    origenId: z.string().optional(),

    descripcion: z.string().min(1),
    procesoIds: z.array(z.string()).default([]),

    evaluacion: EvaluacionRiesgoSchema.optional(),

    tratamiento: TratamientoSchema.optional(),
    /**
     * Obligatoria al aceptar o descartar: son las dos decisiones que no dejan
     * rastro de accion. Un riesgo aceptado sin justificacion es indistinguible
     * de uno olvidado, y es lo primero que un auditor pide explicar.
     */
    justificacionTratamiento: z.string().optional(),

    planAccionId: z.string().optional(),
    responsableId: z.string(),
    estado: EstadoRiesgoOportunidadSchema.default('identificado'),

    fechaIdentificacion: z.string(),
    proximaRevision: z.string().optional(),
  })
  .refine(
    (r) =>
      !['aceptar', 'descartar'].includes(r.tratamiento ?? '') ||
      (r.justificacionTratamiento?.trim().length ?? 0) > 0,
    {
      message: 'Aceptar un riesgo o descartar una oportunidad exige justificacion',
      path: ['justificacionTratamiento'],
    },
  )
  .refine(
    (r) => r.tipo === 'riesgo' || !['evitar', 'mitigar', 'transferir'].includes(r.tratamiento ?? ''),
    {
      message: 'Evitar, mitigar y transferir solo aplican a riesgos',
      path: ['tratamiento'],
    },
  )
  .refine((r) => r.tipo === 'oportunidad' || r.tratamiento !== 'aprovechar', {
    message: 'Aprovechar solo aplica a oportunidades',
    path: ['tratamiento'],
  });
export type RiesgoOportunidad = z.infer<typeof RiesgoOportunidadSchema>;
