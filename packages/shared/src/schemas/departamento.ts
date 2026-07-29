import { z } from 'zod';

/**
 * Tipos de proceso según el enfoque a procesos de ISO 9001 §4.4.
 *
 * La norma exige determinar los procesos del sistema de gestión, su secuencia
 * e interacción. La clasificación habitual en un mapa de procesos es:
 *
 * - **Estratégicos**: dirigen la organización (planificación, revisión por la
 *   dirección, gestión de riesgos). Definen el rumbo, no producen el servicio.
 * - **Operativos** (o de realización): la cadena de valor. Son los que generan
 *   el producto o servicio y los que el cliente percibe.
 * - **Apoyo**: sostienen a los anteriores (RRHH, mantención, TI, compras).
 *
 * Sin esta clasificación no se puede dibujar un mapa de procesos: un
 * departamento suelto es solo un nombre, y el mapa es precisamente la
 * representación de cómo se ordenan e interactúan.
 */
export const TIPOS_PROCESO = [
  {
    codigo: 'estrategico',
    nombre: 'Estratégico',
    // El plural va aparte porque "de apoyo" no se pluraliza como los otros:
    // concatenar "Procesos " + nombre + "s" daría "Procesos de apoyos".
    titulo: 'Procesos estratégicos',
    descripcion: 'Dirigen la organización y definen el rumbo',
  },
  {
    codigo: 'operativo',
    nombre: 'Operativo',
    titulo: 'Procesos operativos',
    descripcion: 'Cadena de valor: generan el producto o servicio',
  },
  {
    codigo: 'apoyo',
    nombre: 'De apoyo',
    titulo: 'Procesos de apoyo',
    descripcion: 'Sostienen a los procesos estratégicos y operativos',
  },
] as const;

export const TipoProcesoSchema = z.enum(['estrategico', 'operativo', 'apoyo']);
export type TipoProceso = z.infer<typeof TipoProcesoSchema>;

/**
 * Departamento / Proceso del Perfil Empresa (RF-11, RF-12, v1.7).
 *
 * Todo Usuario Interno pertenece a uno. Se modela como proceso —y no solo como
 * unidad organizativa— porque es lo que ISO 9001 §4.4 pide identificar, y
 * porque las auditorías se planifican por proceso, no por organigrama.
 *
 * `entradas` y `salidas` son lo que permite representar la interacción entre
 * procesos: sin ellas el mapa sería una lista de cajas sin flechas.
 */
export const DepartamentoSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  nombre: z.string(),
  /** Por defecto operativo: es el caso más común al declarar un área. */
  tipo: TipoProcesoSchema.default('operativo'),
  descripcion: z.string().optional(),
  /** Dueño del proceso. La norma no lo exige por nombre, pero sin responsable no hay a quién auditar. */
  responsableId: z.string().nullable().default(null),
  /** Qué necesita el proceso para operar. */
  entradas: z.array(z.string()).default([]),
  /** Qué entrega a otros procesos o al cliente. */
  salidas: z.array(z.string()).default([]),
});
export type Departamento = z.infer<typeof DepartamentoSchema>;

export function nombreTipoProceso(tipo: TipoProceso): string {
  return TIPOS_PROCESO.find((t) => t.codigo === tipo)?.nombre ?? tipo;
}
