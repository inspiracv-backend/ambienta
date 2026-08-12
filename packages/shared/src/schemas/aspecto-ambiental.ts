import { z } from 'zod';

/**
 * Matriz de aspectos e impactos ambientales — ISO 14001 §6.1.2.
 *
 * Es el eslabon que hoy falta entre el mapa de procesos (§4.4) y la matriz
 * legal (§6.1.3). Sin el no se puede responder la primera pregunta que hace un
 * auditor: como determinaron que una norma les aplica y como saben que no falta
 * ninguna.
 *
 * El orden correcto es actividad -> aspecto -> impacto -> significancia ->
 * requisito legal. Agregar normas a mano a una lista funciona como registro,
 * pero no es defendible.
 */

/**
 * Tipos de aspecto ambiental.
 *
 * `biodiversidad` y `gases_efecto_invernadero` estan explicitos porque ISO
 * 14001:2026 amplia el contexto para incluirlos. En la edicion 2015 habrian
 * caido en `otro`, y eso vuelve imposible reportarlos por separado.
 */
export const TipoAspectoSchema = z.enum([
  'emision_atmosferica',
  'vertido_agua',
  'residuo_solido',
  'residuo_peligroso',
  'consumo_agua',
  'consumo_energia',
  'ruido',
  'contaminacion_suelo',
  'biodiversidad',
  'gases_efecto_invernadero',
  'otro',
]);
export type TipoAspecto = z.infer<typeof TipoAspectoSchema>;

/**
 * §6.1.2 exige considerar las tres condiciones, no solo la normal. Un derrame
 * no ocurre en operacion normal: si el modelo solo admite esa, la matriz omite
 * justamente los aspectos de mayor impacto.
 */
export const CondicionOperacionSchema = z.enum(['normal', 'anormal', 'emergencia']);
export type CondicionOperacion = z.infer<typeof CondicionOperacionSchema>;

/**
 * Perspectiva de ciclo de vida (§6.1.2).
 *
 * Las siete etapas son las que enumera la NOTA 1 de §6.1.2 en
 * NCh-ISO 14001:2026, en su orden: adquisicion de materias primas, diseno,
 * produccion, transporte/entrega, uso, tratamiento al finalizar la vida util y
 * disposicion final.
 *
 * `diseno` importa mas de lo que parece: es la etapa donde la organizacion
 * tiene mayor capacidad de influir sobre el impacto, y es justo la que se suele
 * omitir cuando se modela el ciclo de vida "de la fabrica hacia afuera".
 * Tratamiento al finalizar la vida util y disposicion final se mantienen
 * separadas porque la norma las distingue: recuperar un material no es lo mismo
 * que disponerlo.
 */
export const EtapaCicloVidaSchema = z.enum([
  'materias_primas',
  'diseno',
  'produccion',
  'transporte_entrega',
  'uso',
  'tratamiento_fin_vida',
  'disposicion_final',
]);
export type EtapaCicloVida = z.infer<typeof EtapaCicloVidaSchema>;

export const ETAPAS_CICLO_VIDA: { value: EtapaCicloVida; label: string }[] = [
  { value: 'materias_primas', label: 'Adquisición de materias primas' },
  { value: 'diseno', label: 'Diseño' },
  { value: 'produccion', label: 'Producción' },
  { value: 'transporte_entrega', label: 'Transporte / entrega' },
  { value: 'uso', label: 'Uso' },
  { value: 'tratamiento_fin_vida', label: 'Tratamiento al finalizar la vida útil' },
  { value: 'disposicion_final', label: 'Disposición final' },
];

/**
 * Evaluacion de significancia.
 *
 * Los criterios y el umbral viven en `ConfiguracionMatrices` del tenant, no
 * aca: varian por sector y por madurez del sistema de gestion. Cablearlos
 * obliga a migrar el dia que entre un cliente con su propia metodologia ya
 * auditada, que es el caso normal en una empresa certificada.
 */
export const EvaluacionSignificanciaSchema = z.object({
  criterios: z.array(
    z.object({
      criterioId: z.string(),
      valor: z.number(),
    }),
  ),
  puntaje: z.number(),
  metodoId: z.string(),
  evaluadoPorId: z.string(),
  fecha: z.string(),
  justificacion: z.string().optional(),
});
export type EvaluacionSignificancia = z.infer<typeof EvaluacionSignificanciaSchema>;

export const AspectoAmbientalSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  plantId: z.string(),
  /** Proceso del mapa (`Departamento.id`). Es el origen de la cadena. */
  procesoId: z.string(),

  /** Actividad concreta dentro del proceso. Ej: "Lavado de equipos de envasado". */
  actividad: z.string().min(1),
  /** Que interactua con el ambiente. Ej: "Vertido de agua con detergente". */
  aspecto: z.string().min(1),
  tipoAspecto: TipoAspectoSchema,
  /** Consecuencia ambiental. Ej: "Alteracion de la calidad del cuerpo receptor". */
  impacto: z.string().min(1),

  condicionOperacion: CondicionOperacionSchema,
  etapaCicloVida: EtapaCicloVidaSchema,

  evaluacion: EvaluacionSignificanciaSchema.optional(),
  /** Derivado del puntaje y del umbral del tenant; se guarda para poder filtrar. */
  significativo: z.boolean().default(false),

  /** Trazabilidad hacia adelante en la cadena. Vacios = eslabon sin cerrar. */
  requisitoLegalIds: z.array(z.string()).default([]),
  riesgoOportunidadIds: z.array(z.string()).default([]),

  fechaIdentificacion: z.string(),
  fechaUltimaRevision: z.string().optional(),
  responsableId: z.string().optional(),
});
export type AspectoAmbiental = z.infer<typeof AspectoAmbientalSchema>;

/**
 * Un aspecto significativo sin tratamiento es el hallazgo mas comun en una
 * auditoria de 14001: la empresa identifico el problema y no hizo nada.
 */
export function aspectoSinTratar(aspecto: AspectoAmbiental): boolean {
  return (
    aspecto.significativo &&
    aspecto.requisitoLegalIds.length === 0 &&
    aspecto.riesgoOportunidadIds.length === 0
  );
}
