import { z } from 'zod';

/**
 * Equipos con obligacion legal de inscripcion y de operador habilitado.
 *
 * Sale de la reunion con el especialista: hay que inscribir calderas,
 * generadores y grupos electrogenos, y "cuando hay calderas hay que ver cuando
 * hay habilitados operadores de caldera con ciertos cursos que se deben
 * cumplir; hay distintos modelos de caldera, eso es importante, que este
 * mapeado".
 *
 * Por que necesita entidad propia: un requisito legal que exige operador
 * certificado no se cumple a nivel de planta, se cumple si **esa** persona
 * tiene **ese** curso vigente. Sin el equipo y sin la certificacion con fecha
 * de vencimiento, el sistema no puede avisar que manana la caldera queda sin
 * operador habilitado — que es exactamente el tipo de alerta para el que existe
 * Ambienta.
 */

export const TipoEquipoSchema = z.enum([
  'caldera',
  'generador',
  'grupo_electrogeno',
  'estanque',
  'compresor',
  'otro',
]);
export type TipoEquipo = z.infer<typeof TipoEquipoSchema>;

export const EstadoEquipoSchema = z.enum(['operativo', 'fuera_de_servicio', 'baja']);
export type EstadoEquipo = z.infer<typeof EstadoEquipoSchema>;

/** Inscripcion ante el organismo que corresponda (SEC, Seremi de Salud). */
export const InscripcionEquipoSchema = z.object({
  organismo: z.string(),
  numero: z.string(),
  fecha: z.string(),
  vencimiento: z.string().optional(),
});
export type InscripcionEquipo = z.infer<typeof InscripcionEquipoSchema>;

/** Persona habilitada para operar el equipo, con su competencia y vigencia. */
export const OperadorHabilitadoSchema = z.object({
  usuarioId: z.string(),
  /** Ej: "Operador de caldera clase B". */
  certificacion: z.string(),
  emitidaPor: z.string().optional(),
  vence: z.string().optional(),
});
export type OperadorHabilitado = z.infer<typeof OperadorHabilitadoSchema>;

export const EquipoReguladoSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  plantId: z.string(),
  nombre: z.string().min(1),
  tipo: TipoEquipoSchema,
  marca: z.string().optional(),
  /** El modelo importa: distintos modelos tienen distintas exigencias. */
  modelo: z.string().optional(),
  numeroSerie: z.string().optional(),

  inscripcion: InscripcionEquipoSchema.optional(),
  operadores: z.array(OperadorHabilitadoSchema).default([]),

  requisitoLegalIds: z.array(z.string()).default([]),
  estado: EstadoEquipoSchema.default('operativo'),
});
export type EquipoRegulado = z.infer<typeof EquipoReguladoSchema>;

/**
 * Un equipo operativo sin ningun operador con certificacion vigente esta
 * incumpliendo, aunque su inscripcion este al dia.
 */
export function sinOperadorHabilitado(equipo: EquipoRegulado, hoy: string): boolean {
  if (equipo.estado !== 'operativo') return false;
  return !equipo.operadores.some((op) => !op.vence || op.vence >= hoy);
}
