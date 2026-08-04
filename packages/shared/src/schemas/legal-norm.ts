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

/**
 * Programa de monitoreo que impone un articulo (propuesta
 * `matrices-ambientales-iso-14001`).
 *
 * El D.S. 609 no se cumple o se incumple: fija parametros, limites y
 * frecuencia. Modelarlo como estructura y no como texto libre es lo que permite
 * generar el calendario y detectar que una medicion vencio; en texto libre el
 * sistema no puede avisar nada, que es justo el problema que Ambienta resuelve.
 */
export const ObligacionMonitoreoSchema = z.object({
  parametros: z.array(
    z.object({
      nombre: z.string(),
      unidad: z.string(),
      limiteMaximo: z.number().optional(),
      metodo: z.string().optional(),
    }),
  ),
  frecuencia: z.enum(['diaria', 'semanal', 'mensual', 'trimestral', 'semestral', 'anual']),
  requiereLaboratorioAcreditado: z.boolean().default(false),
  cuerpoReceptor: z.string().optional(),
});
export type ObligacionMonitoreo = z.infer<typeof ObligacionMonitoreoSchema>;

/**
 * Evidencia en soporte fisico.
 *
 * La reunion fue explicita: las empresas no digitalizan, y "igual debe existir
 * papel a resguardo o administrado segun empresa". `evidenciaUrl` asume
 * digital y deja fuera el caso mayoritario.
 */
export const EvidenciaFisicaSchema = z.object({
  ubicacion: z.string(),
  custodioId: z.string().optional(),
  referencia: z.string().optional(),
});
export type EvidenciaFisica = z.infer<typeof EvidenciaFisicaSchema>;

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

  // --- Campos de `matrices-ambientales-iso-14001` (flag `matricesIso`) ---
  // Opcionales a proposito: la matriz legal actual valida igual sin ellos.
  obligacionMonitoreo: ObligacionMonitoreoSchema.optional(),
  evidenciaFisica: EvidenciaFisicaSchema.optional(),
  /** Requisitos anclados a un activo concreto (caldera, generador). */
  equipoIds: z.array(z.string()).optional(),
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
/**
 * §6.1.3 de NCh-ISO 14001:2026 se titula "obligaciones de compliance" — el
 * termino que reemplaza a "requisitos legales y otros requisitos" de la edicion
 * 2015. Dentro de esa categoria conviven dos cosas que no son lo mismo: la ley,
 * y lo que la organizacion decide cumplir (APL, requisitos del cliente,
 * compromisos voluntarios). Confundirlas distorsiona el indicador de
 * cumplimiento legal, por eso el eje se mantiene separado.
 */
export const CategoriaRequisitoSchema = z.enum(['legal', 'otro_requisito']);
export type CategoriaRequisito = z.infer<typeof CategoriaRequisitoSchema>;

export const SubtipoRequisitoSchema = z.enum([
  'ley',
  'decreto',
  'resolucion',
  'rca',
  'permiso_sectorial',
  'iso',
  'apl',
  'requisito_cliente',
  'compromiso_voluntario',
]);
export type SubtipoRequisito = z.infer<typeof SubtipoRequisitoSchema>;

/** Una norma derogada sigue importando: hay que saber que dejo de aplicar y desde cuando. */
export const VigenciaNormaSchema = z.object({
  estado: z.enum(['vigente', 'derogada', 'modificada', 'proyecto']),
  desde: z.string().optional(),
  hasta: z.string().optional(),
  reemplazaANormaId: z.string().optional(),
  reemplazadaPorNormaId: z.string().optional(),
});
export type VigenciaNorma = z.infer<typeof VigenciaNormaSchema>;

/**
 * Por que aplica esta norma a esta empresa.
 *
 * Hoy alguien agrega normas a mano a una lista. Eso funciona como registro pero
 * no responde la primera pregunta de un auditor: como determinaron que les
 * aplica y como saben que no falta ninguna. `aspectoAmbientalIds` es ese "por
 * que" trazable; `actividadesEconomicas` permite la precarga por rubro.
 */
export const AplicabilidadSchema = z.object({
  determinadaPor: z.enum(['automatica', 'manual']).default('manual'),
  /** Codigos CIIU de las actividades a las que aplica. */
  actividadesEconomicas: z.array(z.string()).default([]),
  criterio: z.string().optional(),
  aspectoAmbientalIds: z.array(z.string()).default([]),
});
export type Aplicabilidad = z.infer<typeof AplicabilidadSchema>;

/** §9.1.2 exige la evaluación de compliance legal de forma periodica, no una sola vez. */
export const EvaluacionPeriodicaSchema = z.object({
  frecuenciaMeses: z.number().int().positive(),
  ultimaEvaluacion: z.string().optional(),
  proximaEvaluacion: z.string().optional(),
});
export type EvaluacionPeriodica = z.infer<typeof EvaluacionPeriodicaSchema>;

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

  // --- Campos de `matrices-ambientales-iso-14001` (flag `matricesIso`) ---
  // Todos opcionales: sin ellos el modelo actual valida sin migracion.
  categoriaRequisito: CategoriaRequisitoSchema.optional(),
  subtipo: SubtipoRequisitoSchema.optional(),
  /** SMA, SEC, SISS, Seremi de Salud, DGA. */
  organismoFiscalizador: z.string().optional(),
  vigencia: VigenciaNormaSchema.optional(),
  aplicabilidad: AplicabilidadSchema.optional(),
  evaluacionPeriodica: EvaluacionPeriodicaSchema.optional(),
});
export type LegalNorm = z.infer<typeof LegalNormSchema>;
