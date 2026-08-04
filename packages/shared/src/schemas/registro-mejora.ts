import { z } from 'zod';

/**
 * Registro de Mejora — entidad raiz del ciclo de tratamiento.
 *
 * Propuesta `hallazgos-auditoria-no-conformidades`, revision 2. Reemplaza el
 * supuesto de que todo lo que se registra es una no conformidad.
 *
 * Dos ejes que NO se fusionan:
 *
 * - `tipo`: que clausula aplica. Son cinco clausulas distintas, no cinco
 *   sabores de lo mismo.
 * - `origenDeteccion`: como se detecto. La auditoria es una de cinco formas,
 *   y en el sistema del cliente la mayoria de los registros NO nace de una.
 *
 * Fusionarlos en un campo produce valores sin sentido: una conformidad no abre
 * registro, y un reclamo de cliente no tiene clasificacion de auditoria.
 */

/**
 * Los cinco tipos del desplegable `Tipo Registro` de la aplicacion del cliente,
 * cada uno anclado a la clausula que lo regula.
 */
export const TipoRegistroMejoraSchema = z.enum([
  'salida_no_conforme', // ISO 9001 §8.7 — control de salidas no conformes
  'no_conformidad', // ISO 9001 §10.2
  'riesgo', // §6.1 / ISO 14001 §6.1.4
  'oportunidad', // §6.1 / ISO 14001 §6.1.4
  'reclamo', // ISO 9001 §9.1.2 — satisfaccion del cliente
]);
export type TipoRegistroMejora = z.infer<typeof TipoRegistroMejoraSchema>;

export const TIPOS_REGISTRO_MEJORA: {
  value: TipoRegistroMejora;
  label: string;
  clausula: string;
}[] = [
  { value: 'salida_no_conforme', label: 'Salida No Conforme', clausula: 'ISO 9001 §8.7' },
  { value: 'no_conformidad', label: 'No Conformidad', clausula: 'ISO 9001 §10.2' },
  { value: 'riesgo', label: 'Riesgo', clausula: 'ISO 14001 §6.1.4' },
  { value: 'oportunidad', label: 'Oportunidad', clausula: 'ISO 14001 §6.1.4' },
  { value: 'reclamo', label: 'Reclamo', clausula: 'ISO 9001 §9.1.2' },
];

/** Los cinco valores del desplegable `Tipo de Deteccion`. */
export const OrigenDeteccionSchema = z.enum([
  'interna',
  'externa',
  'analisis_foda',
  'auditoria_interna',
  'auditoria_externa',
]);
export type OrigenDeteccion = z.infer<typeof OrigenDeteccionSchema>;

export const ORIGENES_DETECCION: { value: OrigenDeteccion; label: string }[] = [
  { value: 'interna', label: 'Interna' },
  { value: 'externa', label: 'Externa' },
  { value: 'analisis_foda', label: 'Análisis FODA' },
  { value: 'auditoria_interna', label: 'Auditoría Interna' },
  { value: 'auditoria_externa', label: 'Auditoría Externa' },
];

/** Etapas del ciclo de tratamiento. El orden efectivo es configurable por tenant. */
export const EtapaMejoraSchema = z.enum([
  'registro',
  'correccion',
  'analisis_causa',
  'accion_correctiva',
  'seguimiento',
  'cerrado',
]);
export type EtapaMejora = z.infer<typeof EtapaMejoraSchema>;

/** Datos del producto — obligatorios si el tipo es salida no conforme (§8.7). */
export const ProductoNoConformeSchema = z.object({
  sku: z.string().min(1),
  lote: z.string().min(1),
  nombre: z.string().min(1),
  cantidad: z.number().nonnegative(),
  unidad: z.string().min(1),
});
export type ProductoNoConforme = z.infer<typeof ProductoNoConformeSchema>;

/** Datos del reclamo — obligatorios si el tipo es reclamo (§9.1.2). */
export const DatosReclamoSchema = z.object({
  clienteNombre: z.string().min(1),
  canal: z.string().min(1),
  fechaReclamo: z.string(),
  clienteId: z.string().optional(),
});
export type DatosReclamo = z.infer<typeof DatosReclamoSchema>;

export const RegistroMejoraSchema = z
  .object({
    id: z.string(),
    tenantId: z.string(),
    plantId: z.string(),
    codigo: z.string(),

    tipo: TipoRegistroMejoraSchema,
    origenDeteccion: OrigenDeteccionSchema,
    /** Obligatorio cuando el origen es una auditoria: es el hallazgo que lo genero. */
    hallazgoId: z.string().optional(),

    fecha: z.string(),
    reportadoPorId: z.string(),
    descripcion: z.string().min(1),
    /** Procesos involucrados — `Departamento.id` del mapa de procesos (§4.4). */
    procesoIds: z.array(z.string()).default([]),
    adjuntosUrls: z.array(z.string()).default([]),

    producto: ProductoNoConformeSchema.optional(),
    reclamo: DatosReclamoSchema.optional(),

    etapaActual: EtapaMejoraSchema.default('registro'),

    /** Un responsable por etapa, asignados desde el alta. */
    responsables: z.object({
      analisisCausaId: z.string(),
      accionCorrectivaId: z.string(),
      seguimientoId: z.string(),
    }),
  })
  .refine((r) => r.tipo !== 'salida_no_conforme' || r.producto !== undefined, {
    message: 'Una salida no conforme exige identificar el producto (§8.7)',
    path: ['producto'],
  })
  .refine((r) => r.tipo !== 'reclamo' || r.reclamo !== undefined, {
    message: 'Un reclamo exige identificar al cliente y el canal',
    path: ['reclamo'],
  })
  .refine(
    (r) =>
      !['auditoria_interna', 'auditoria_externa'].includes(r.origenDeteccion) ||
      r.hallazgoId !== undefined,
    {
      message: 'Un registro detectado en auditoría debe apuntar a su hallazgo',
      path: ['hallazgoId'],
    },
  );
export type RegistroMejora = z.infer<typeof RegistroMejoraSchema>;

// ---------------------------------------------------------------------------
// Etapas del tratamiento
// ---------------------------------------------------------------------------

/**
 * Metodologias de analisis de causa.
 *
 * El desplegable del cliente tiene exactamente dos opciones. `forma` define que
 * formulario se renderiza; `texto_libre` es el escape para que otra empresa
 * agregue la suya (arbol de fallos, Pareto) sin cambiar el schema.
 */
export const FormaMetodologiaSchema = z.enum(['cinco_porques', 'espina_pescado', 'texto_libre']);
export type FormaMetodologia = z.infer<typeof FormaMetodologiaSchema>;

export const METODOLOGIAS_ANALISIS_CAUSA: {
  id: string;
  nombre: string;
  forma: FormaMetodologia;
}[] = [
  { id: 'cinco-porques', nombre: '5 Por Qué', forma: 'cinco_porques' },
  { id: 'diagrama-pescado', nombre: 'Diagrama de Pescado', forma: 'espina_pescado' },
];

/** §10.2.1 a) — reaccionar y contener. */
export const EtapaCorreccionSchema = z.object({
  correccionInmediata: z.string(),
  fechaEjecucion: z.string().optional(),
  evidencia: z.string().optional(),
  evidenciaUrls: z.array(z.string()).default([]),
  responsableEtapaId: z.string().optional(),
});
export type EtapaCorreccion = z.infer<typeof EtapaCorreccionSchema>;

/** §10.2.1 b) — analizar la causa, con metodologia seleccionable. */
export const EtapaAnalisisCausaSchema = z
  .object({
    metodologiaId: z.string(),
    /** Un texto libre por escalon: asi lo usa el cliente, mezclando pregunta y respuesta. */
    cincoPorques: z.array(z.string()).max(5).default([]),
    espinaPescado: z
      .object({
        causas: z.array(z.object({ texto: z.string(), categoria: z.string().optional() })),
      })
      .optional(),
    causaRaiz: z.string(),
    responsableEtapaId: z.string().optional(),
    fechaEjecucion: z.string().optional(),
  })
  .refine(
    (e) =>
      e.metodologiaId !== 'cinco-porques' || e.cincoPorques.some((p) => p.trim().length > 0),
    { message: 'Con 5 Por Qué hay que completar al menos un escalón', path: ['cincoPorques'] },
  )
  .refine(
    (e) =>
      e.metodologiaId !== 'diagrama-pescado' ||
      (e.espinaPescado?.causas.length ?? 0) > 0,
    { message: 'El Diagrama de Pescado necesita al menos una causa', path: ['espinaPescado'] },
  );
export type EtapaAnalisisCausa = z.infer<typeof EtapaAnalisisCausaSchema>;

/** §10.2.1 b y c). El cliente la rotula "Etapa de Capa". */
export const EtapaAccionCorrectivaSchema = z.object({
  severidad: z.string(),
  tipoAccion: z.enum(['correctiva', 'preventiva']),
  descripcionAccion: z.string(),
  evidenciaAccion: z.string().optional(),
  causaRaiz: z.string().optional(),
  fechaInicial: z.string().optional(),
  fechaFinalizacion: z.string().optional(),
  planAccionId: z.string().optional(),
  responsableEtapaId: z.string().optional(),
  evidenciaUrls: z.array(z.string()).default([]),
});
export type EtapaAccionCorrectiva = z.infer<typeof EtapaAccionCorrectivaSchema>;

/**
 * §10.2.1 d, e y f — verificar la eficacia.
 *
 * Los cinco campos son tri-estado (`null` = sin responder). En la aplicacion
 * del cliente son desplegables `Seleccione… / SI / NO`, y modelarlos como
 * booleano convierte "todavia no lo verifique" en "No", que en tres de las
 * cuatro preguntas es la respuesta favorable: el default silencioso cerraria
 * la verificacion a favor.
 */
/**
 * Salidas reglamentarias del tratamiento.
 *
 * Responder SI a las preguntas de §10.2.1 e) y f) no es un dato: es un
 * compromiso. La norma pide actualizar los riesgos y oportunidades y hacer los
 * cambios al sistema de gestion cuando corresponda, asi que el SI tiene que
 * dejar una salida pendiente y trazable.
 *
 * Sin esto, alguien marca SI, cierra la no conformidad, y el sistema no vuelve
 * a mencionarlo nunca — que es exactamente el hallazgo que levanta un auditor
 * al revisar la eficacia del propio sistema de gestion.
 */
export const TipoSalidaSchema = z.enum([
  'matriz_riesgos', // §6.1.4 — actualizar la matriz de riesgos y oportunidades
  'matriz_foda', // Analisis FODA de la revision anual (ISO 9001 §4.1)
  'documento_sgc', // Procedimiento o instructivo del sistema de gestion
]);
export type TipoSalida = z.infer<typeof TipoSalidaSchema>;

export const SALIDAS_REGLAMENTARIAS: {
  value: TipoSalida;
  label: string;
  descripcion: string;
}[] = [
  {
    value: 'matriz_riesgos',
    label: 'Actualizar matriz de riesgos y oportunidades',
    descripcion: 'El tratamiento cambió el nivel de un riesgo o abrió uno nuevo.',
  },
  {
    value: 'matriz_foda',
    label: 'Actualizar matriz FODA',
    descripcion: 'El hallazgo altera una fortaleza, debilidad, oportunidad o amenaza.',
  },
  {
    value: 'documento_sgc',
    label: 'Modificar documento del SGC',
    descripcion: 'Hay que cambiar un procedimiento o un instructivo de trabajo.',
  },
];

export const SalidaTratamientoSchema = z.object({
  tipo: TipoSalidaSchema,
  descripcion: z.string(),
  responsableId: z.string().optional(),
  fechaCompromiso: z.string().optional(),
  /** Entidad destino cuando ya se ejecutó (riesgo, documento, ítem FODA). */
  entidadDestinoId: z.string().optional(),
  estado: z.enum(['pendiente', 'ejecutada', 'descartada']).default('pendiente'),
  justificacionDescarte: z.string().optional(),
});
export type SalidaTratamiento = z.infer<typeof SalidaTratamientoSchema>;

export const EtapaSeguimientoSchema = z.object({
  eficaz: z.boolean().nullable().default(null),
  causaSeRepitio: z.boolean().nullable().default(null),
  cumplioProposito: z.boolean().nullable().default(null),
  requiereActualizarRiesgos: z.boolean().nullable().default(null),
  requiereCambiosSGC: z.boolean().nullable().default(null),
  requiereActualizarFoda: z.boolean().nullable().default(null),
  /** Se derivan de las tres preguntas anteriores cuando la respuesta es SI. */
  salidas: z.array(SalidaTratamientoSchema).default([]),
  observaciones: z.string().optional(),
  fechaSeguimiento: z.string().optional(),
  responsableEtapaId: z.string().optional(),
  evidenciaUrls: z.array(z.string()).default([]),
});
export type EtapaSeguimiento = z.infer<typeof EtapaSeguimientoSchema>;

/**
 * Qué salidas quedan comprometidas segun las respuestas del seguimiento.
 *
 * Solo `true` compromete: `null` es "sin responder" y no obliga a nada, que es
 * distinto de un NO explicito.
 */
export function salidasComprometidas(seguimiento: EtapaSeguimiento): TipoSalida[] {
  const salidas: TipoSalida[] = [];
  if (seguimiento.requiereActualizarRiesgos === true) salidas.push('matriz_riesgos');
  if (seguimiento.requiereActualizarFoda === true) salidas.push('matriz_foda');
  if (seguimiento.requiereCambiosSGC === true) salidas.push('documento_sgc');
  return salidas;
}

/**
 * Salidas comprometidas que siguen sin resolverse.
 *
 * Hoy se muestran como advertencia en la etapa de seguimiento. La decision de
 * si ademas deben bloquear el cierre queda abierta: de nada sirve declarar que
 * hay que actualizar la matriz de riesgos si despues se cierra el caso sin
 * hacerlo, pero bloquear obliga a resolver la salida antes de firmar y eso
 * puede no ser el orden real de trabajo. Descartarla es valido y exige
 * justificacion escrita.
 */
export function salidasPendientes(seguimiento: EtapaSeguimiento): TipoSalida[] {
  const comprometidas = salidasComprometidas(seguimiento);
  return comprometidas.filter((tipo) => {
    const salida = seguimiento.salidas.find((s) => s.tipo === tipo);
    return !salida || salida.estado === 'pendiente';
  });
}

export const EtapasMejoraSchema = z.object({
  correccion: EtapaCorreccionSchema.optional(),
  analisisCausa: EtapaAnalisisCausaSchema.optional(),
  accionCorrectiva: EtapaAccionCorrectivaSchema.optional(),
  seguimiento: EtapaSeguimientoSchema.optional(),
});
export type EtapasMejora = z.infer<typeof EtapasMejoraSchema>;

/** El cierre exige eficacia verificada, no solo firma (§10.2.1 d). */
export function puedeCerrarse(seguimiento?: EtapaSeguimiento): boolean {
  return seguimiento?.eficaz === true;
}

/**
 * Riesgo y oportunidad saltan correccion y analisis de causa: no hay
 * "correccion inmediata" de una oportunidad. Recorrer las cinco etapas con
 * campos vacios seria peor dato que reconocer el flujo corto.
 */
export function etapasAplicables(tipo: TipoRegistroMejora): EtapaMejora[] {
  if (tipo === 'riesgo' || tipo === 'oportunidad') {
    return ['registro', 'accion_correctiva', 'seguimiento', 'cerrado'];
  }
  return ['registro', 'correccion', 'analisis_causa', 'accion_correctiva', 'seguimiento', 'cerrado'];
}
