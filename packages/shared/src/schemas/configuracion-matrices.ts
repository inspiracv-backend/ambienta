import { z } from 'zod';

/**
 * Configuracion por tenant de las matrices ambientales.
 *
 * Los criterios de significancia y el metodo de evaluacion de riesgos varian
 * por sector y por la madurez del sistema de gestion. Cablearlos obliga a
 * migrar el dia que entre un cliente con su propia metodologia ya auditada,
 * que es el caso normal en una empresa certificada.
 *
 * Mismo criterio que se aplico a la escala de severidad en la propuesta
 * `hallazgos-auditoria-no-conformidades`: lo trazable a una clausula va fijo,
 * lo que es convencion de empresa va configurable.
 */

/** Como se combina el puntaje de los criterios para decidir significancia. */
export const MetodoSignificanciaSchema = z.enum(['suma', 'producto', 'promedio']);
export type MetodoSignificancia = z.infer<typeof MetodoSignificanciaSchema>;

export const CriterioSignificanciaSchema = z.object({
  id: z.string(),
  nombre: z.string(),
  descripcion: z.string().optional(),
  /** Valores admitidos, de menor a mayor gravedad. */
  escala: z.array(z.object({ valor: z.number(), etiqueta: z.string() })).min(2),
  /** Peso relativo; 1 si todos pesan igual. */
  peso: z.number().default(1),
});
export type CriterioSignificancia = z.infer<typeof CriterioSignificanciaSchema>;

export const ConfiguracionMatricesSchema = z.object({
  tenantId: z.string(),

  /** §6.1.2 — como se decide que un aspecto es significativo. */
  criteriosSignificancia: z.array(CriterioSignificanciaSchema).default([]),
  metodoSignificancia: MetodoSignificanciaSchema.default('producto'),
  /** A partir de este puntaje, el aspecto es significativo. */
  umbralSignificancia: z.number().default(0),

  /** §6.1.1 — matriz probabilidad x consecuencia. */
  escalaProbabilidad: z.array(z.object({ valor: z.number(), etiqueta: z.string() })).default([]),
  escalaConsecuencia: z.array(z.object({ valor: z.number(), etiqueta: z.string() })).default([]),
  /** Umbral inferior de cada nivel, sobre el producto probabilidad x consecuencia. */
  umbralesNivelRiesgo: z
    .object({ medio: z.number(), alto: z.number(), critico: z.number() })
    .optional(),

  /** §9.1.2 — cada cuanto se reevalua el cumplimiento legal por defecto. */
  frecuenciaEvaluacionLegalMeses: z.number().int().positive().default(12),
});
export type ConfiguracionMatrices = z.infer<typeof ConfiguracionMatricesSchema>;

/**
 * Calcula el puntaje de significancia segun el metodo del tenant.
 *
 * Se expone como funcion y no como campo calculado porque el puntaje debe
 * poder recalcularse cuando cambian los criterios, sin reescribir cada aspecto.
 */
export function calcularPuntajeSignificancia(
  valores: { criterioId: string; valor: number }[],
  criterios: CriterioSignificancia[],
  metodo: MetodoSignificancia,
): number {
  if (valores.length === 0) return 0;
  const ponderados = valores.map((v) => {
    const criterio = criterios.find((c) => c.id === v.criterioId);
    return v.valor * (criterio?.peso ?? 1);
  });

  if (metodo === 'suma') return ponderados.reduce((a, b) => a + b, 0);
  if (metodo === 'promedio') return ponderados.reduce((a, b) => a + b, 0) / ponderados.length;
  return ponderados.reduce((a, b) => a * b, 1);
}
