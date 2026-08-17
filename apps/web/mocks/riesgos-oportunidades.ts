import type { RiesgoOportunidad, EquipoRegulado } from '@ambienta/shared';

/**
 * Matriz de riesgos y oportunidades (ISO 14001 §6.1.1).
 *
 * Los dos primeros nacen de aspectos ambientales significativos, que es el
 * camino que pide la norma. `ryo-3` nace del contexto y `ryo-4` del cambio
 * climatico, que la edicion 2026 incorpora explicitamente — sin ellos la matriz
 * pareceria depender solo de los aspectos, y §6.1.1 tambien deriva del contexto
 * y de las partes interesadas.
 */
export const mockRiesgosOportunidades: RiesgoOportunidad[] = [
  {
    id: 'ryo-1',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    codigo: 'R-2026-01',
    tipo: 'riesgo',
    origen: 'aspecto_ambiental',
    origenId: 'asp-1',
    descripcion:
      'Superar el limite de cloro libre en la descarga y ser sancionado por la Superintendencia.',
    procesoIds: ['depto-operaciones'],
    evaluacion: {
      probabilidad: 3,
      consecuencia: 3,
      nivel: 'alto',
      metodoId: 'prob-x-consec',
      fecha: '2026-03-20',
    },
    tratamiento: 'mitigar',
    planAccionId: 'plan-1',
    responsableId: 'user-encargado',
    estado: 'en_tratamiento',
    fechaIdentificacion: '2026-03-20',
    proximaRevision: '2026-09-20',
  },
  {
    id: 'ryo-2',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    codigo: 'R-2026-02',
    tipo: 'riesgo',
    origen: 'aspecto_ambiental',
    origenId: 'asp-3',
    descripcion: 'Derrame de hipoclorito por falla de contencion secundaria del estanque.',
    procesoIds: ['depto-operaciones'],
    evaluacion: {
      probabilidad: 2,
      consecuencia: 4,
      nivel: 'alto',
      metodoId: 'prob-x-consec',
      fecha: '2026-03-20',
    },
    tratamiento: 'evitar',
    responsableId: 'user-encargado',
    estado: 'identificado',
    fechaIdentificacion: '2026-03-20',
    proximaRevision: '2026-09-20',
  },
  {
    id: 'ryo-3',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    codigo: 'O-2026-01',
    tipo: 'oportunidad',
    origen: 'contexto',
    descripcion:
      'Recircular el agua de lavado para reducir consumo y carga de la descarga.',
    procesoIds: ['depto-operaciones'],
    evaluacion: {
      probabilidad: 3,
      consecuencia: 3,
      nivel: 'alto',
      metodoId: 'prob-x-consec',
      fecha: '2026-04-02',
    },
    tratamiento: 'aprovechar',
    responsableId: 'user-admin-empresa',
    estado: 'en_tratamiento',
    fechaIdentificacion: '2026-04-02',
  },
  {
    id: 'ryo-4',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    codigo: 'R-2026-03',
    tipo: 'riesgo',
    origen: 'cambio_climatico',
    descripcion:
      'Restriccion de extraccion de agua por decreto de escasez hidrica en la cuenca.',
    procesoIds: ['depto-operaciones', 'depto-direccion'],
    evaluacion: {
      probabilidad: 3,
      consecuencia: 4,
      nivel: 'critico',
      metodoId: 'prob-x-consec',
      fecha: '2026-04-02',
    },
    // Aceptado: la justificacion es obligatoria y el schema lo valida.
    tratamiento: 'aceptar',
    justificacionTratamiento:
      'Sin alternativa tecnica en el corto plazo; se monitorea el estado de la cuenca y se revisa cada trimestre.',
    responsableId: 'user-admin-empresa',
    estado: 'identificado',
    fechaIdentificacion: '2026-04-02',
    proximaRevision: '2026-07-02',
  },
];

/**
 * Equipos regulados.
 *
 * La caldera tiene un operador cuya certificacion vence pronto: es el caso que
 * justifica modelar la competencia con fecha, porque un equipo operativo sin
 * operador habilitado esta incumpliendo aunque su inscripcion este al dia.
 */
export const mockEquiposRegulados: EquipoRegulado[] = [
  {
    id: 'equipo-1',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    nombre: 'Caldera de vapor N.1',
    tipo: 'caldera',
    marca: 'Thermal',
    modelo: 'TH-450',
    numeroSerie: 'TH450-2019-0142',
    inscripcion: {
      organismo: 'SEC',
      numero: 'CAL-2019-0142',
      fecha: '2019-08-14',
      vencimiento: '2027-08-14',
    },
    operadores: [
      {
        usuarioId: 'user-encargado',
        certificacion: 'Operador de caldera clase B',
        emitidaPor: 'SEC',
        vence: '2026-09-30',
      },
    ],
    requisitoLegalIds: [],
    estado: 'operativo',
  },
  {
    id: 'equipo-2',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    nombre: 'Grupo electrogeno de respaldo',
    tipo: 'grupo_electrogeno',
    marca: 'PowerGen',
    modelo: 'PG-250',
    inscripcion: {
      organismo: 'SEC',
      numero: 'GE-2021-0873',
      fecha: '2021-02-03',
    },
    operadores: [],
    requisitoLegalIds: [],
    estado: 'operativo',
  },
];
