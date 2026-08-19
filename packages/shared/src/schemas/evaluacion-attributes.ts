import { z } from 'zod';

/**
 * Lo que puede vivir dentro de `article_compliance.attributes`.
 *
 * Es un jsonb, asi que la base acepta cualquier cosa. Sin un esquema declarado
 * se convierte en un cajon: dos pantallas escriben claves distintas, nadie sabe
 * que contiene, y no hay forma de validarlo ni de documentarlo. Es el mismo
 * caso que `tenants.settings`, y se resuelve igual.
 *
 * ## Por que `incluidoEnCalculo` vive aca y no en una columna
 *
 * RF-24 pide poder excluir un articulo del porcentaje de cumplimiento. Es una
 * decision que todavia esta tomando forma —hoy es por instalacion, y podria
 * pasar a ser por empresa— asi que una columna obligaria a una migracion por
 * cada ajuste. Cuando se estabilice, merece columna: un jsonb no se indexa ni
 * se restringe, y este es justo el dato sobre el que se va a querer consultar.
 *
 * **Ese costo esta anotado a proposito**: la alternativa era decidirlo mal
 * ahora y quedar con una columna que hay que migrar dos veces.
 */
export const EvaluacionAttributesSchema = z.object({
  /**
   * Si este articulo cuenta para el porcentaje de cumplimiento (RF-24).
   *
   * Ausente significa **incluido**: es el estado por defecto, y guardar `true`
   * en cada uno de miles de articulos seria ruido. Solo se escribe cuando
   * alguien decide excluirlo.
   */
  incluidoEnCalculo: z.boolean().optional(),
  /** Por que se excluyo. Obligatorio de hecho: excluir sin motivo es indistinguible de un error. */
  motivoExclusion: z.string().max(500).optional(),
});

export type EvaluacionAttributes = z.infer<typeof EvaluacionAttributesSchema>;

/**
 * Lee `attributes` sin confiar en su forma.
 *
 * Puede haber filas creadas antes de que este esquema existiera, o con claves
 * escritas a mano. **Una clave invalida no debe tumbar la carga de la matriz
 * entera**: se descarta lo que no calza y se conserva lo que si.
 */
export function leerEvaluacionAttributes(crudo: unknown): EvaluacionAttributes {
  if (!crudo || typeof crudo !== 'object' || Array.isArray(crudo)) return {};

  const parcial = EvaluacionAttributesSchema.safeParse(crudo);
  if (parcial.success) return parcial.data;

  // Clave por clave: se rescata lo valido en vez de perderlo todo por una
  // entrada mala.
  const rescatado: Record<string, unknown> = {};
  for (const [clave, valor] of Object.entries(crudo as Record<string, unknown>)) {
    const forma = EvaluacionAttributesSchema.shape[
      clave as keyof EvaluacionAttributes
    ];
    if (forma && forma.safeParse(valor).success) rescatado[clave] = valor;
  }
  return EvaluacionAttributesSchema.parse(rescatado);
}

/**
 * Si este articulo cuenta para el porcentaje.
 *
 * **Ausente es incluido.** Confundir "no dice nada" con "excluido" sacaria del
 * calculo a todos los articulos que nadie toco nunca — o sea casi todos— y el
 * porcentaje quedaria calculado sobre un punado de filas.
 */
export function cuentaParaElCalculo(attributes: unknown): boolean {
  return leerEvaluacionAttributes(attributes).incluidoEnCalculo !== false;
}

/**
 * Fusiona un cambio con lo que ya estaba guardado.
 *
 * **Nunca reemplaza.** Mandar el objeto entero desde una pantalla borraria lo
 * que escribieron las otras, y el destrozo solo se veria al recargar una
 * tercera. Es exactamente el error que ya se corrigio en `tenants.settings`.
 */
export function fusionarAttributes(
  guardado: unknown,
  parche: EvaluacionAttributes,
): EvaluacionAttributes {
  return { ...leerEvaluacionAttributes(guardado), ...parche };
}
