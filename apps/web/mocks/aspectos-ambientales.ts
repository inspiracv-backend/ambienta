import type { AspectoAmbiental, ConfiguracionMatrices } from '@ambienta/shared';

/**
 * Criterios de significancia de ejemplo (ISO 14001 §6.1.2).
 *
 * Cuatro criterios de 1 a 3 con metodo `producto` y umbral 18 — con eso, un
 * aspecto necesita puntuar alto en mas de un criterio para ser significativo.
 * Es una metodologia habitual, no la unica: por eso vive en configuracion.
 */
export const mockConfiguracionMatrices: ConfiguracionMatrices = {
  tenantId: 'a0000000-0000-0000-0000-000000000001',
  criteriosSignificancia: [
    {
      id: 'crit-severidad',
      nombre: 'Severidad del impacto',
      descripcion: 'Magnitud del dano ambiental si el aspecto se materializa.',
      escala: [
        { valor: 1, etiqueta: 'Leve' },
        { valor: 2, etiqueta: 'Moderada' },
        { valor: 3, etiqueta: 'Grave' },
      ],
      peso: 1,
    },
    {
      id: 'crit-frecuencia',
      nombre: 'Frecuencia',
      descripcion: 'Cada cuanto ocurre la actividad que genera el aspecto.',
      escala: [
        { valor: 1, etiqueta: 'Ocasional' },
        { valor: 2, etiqueta: 'Periodica' },
        { valor: 3, etiqueta: 'Continua' },
      ],
      peso: 1,
    },
    {
      id: 'crit-alcance',
      nombre: 'Alcance',
      descripcion: 'Hasta donde llega el impacto.',
      escala: [
        { valor: 1, etiqueta: 'Puntual' },
        { valor: 2, etiqueta: 'Local' },
        { valor: 3, etiqueta: 'Extendido' },
      ],
      peso: 1,
    },
    {
      id: 'crit-legal',
      nombre: 'Requisito legal asociado',
      descripcion: 'Si existe normativa que regule el aspecto.',
      escala: [
        { valor: 1, etiqueta: 'Sin requisito' },
        { valor: 3, etiqueta: 'Con requisito exigible' },
      ],
      peso: 1,
    },
  ],
  metodoSignificancia: 'producto',
  umbralSignificancia: 18,
  escalaProbabilidad: [
    { valor: 1, etiqueta: 'Improbable' },
    { valor: 2, etiqueta: 'Posible' },
    { valor: 3, etiqueta: 'Probable' },
    { valor: 4, etiqueta: 'Casi seguro' },
  ],
  escalaConsecuencia: [
    { valor: 1, etiqueta: 'Menor' },
    { valor: 2, etiqueta: 'Moderada' },
    { valor: 3, etiqueta: 'Mayor' },
    { valor: 4, etiqueta: 'Critica' },
  ],
  umbralesNivelRiesgo: { medio: 4, alto: 8, critico: 12 },
  frecuenciaEvaluacionLegalMeses: 12,
};

/**
 * Aspectos ambientales de ejemplo.
 *
 * Cubren a proposito las tres condiciones de operacion: la norma exige
 * considerar la anormal y la de emergencia, y con solo aspectos en condicion
 * normal la matriz omite precisamente los de mayor impacto. El derrame de
 * hipoclorito existe para representar ese caso.
 */
export const mockAspectosAmbientales: AspectoAmbiental[] = [
  {
    id: 'asp-1',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    procesoId: 'depto-operaciones',
    actividad: 'Lavado de equipos de envasado',
    aspecto: 'Vertido de agua con residuos de detergente y cloro',
    tipoAspecto: 'vertido_agua',
    impacto: 'Alteracion de la calidad del cuerpo receptor',
    condicionOperacion: 'normal',
    etapaCicloVida: 'produccion',
    evaluacion: {
      criterios: [
        { criterioId: 'crit-severidad', valor: 2 },
        { criterioId: 'crit-frecuencia', valor: 3 },
        { criterioId: 'crit-alcance', valor: 2 },
        { criterioId: 'crit-legal', valor: 3 },
      ],
      puntaje: 36,
      metodoId: 'producto',
      evaluadoPorId: 'user-admin-empresa',
      fecha: '2026-03-12',
      justificacion: 'Descarga continua a cuerpo receptor regulado por el D.S. 609.',
    },
    significativo: true,
    requisitoLegalIds: ['norm-ds609'],
    riesgoOportunidadIds: ['ryo-1'],
    fechaIdentificacion: '2026-03-12',
    fechaUltimaRevision: '2026-07-01',
    responsableId: 'user-admin-empresa',
  },
  {
    id: 'asp-2',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    procesoId: 'depto-operaciones',
    actividad: 'Operacion de caldera a gas',
    aspecto: 'Emision de gases de combustion',
    tipoAspecto: 'gases_efecto_invernadero',
    impacto: 'Contribucion al cambio climatico',
    condicionOperacion: 'normal',
    etapaCicloVida: 'produccion',
    evaluacion: {
      criterios: [
        { criterioId: 'crit-severidad', valor: 2 },
        { criterioId: 'crit-frecuencia', valor: 3 },
        { criterioId: 'crit-alcance', valor: 3 },
        { criterioId: 'crit-legal', valor: 3 },
      ],
      puntaje: 54,
      metodoId: 'producto',
      evaluadoPorId: 'user-admin-empresa',
      fecha: '2026-03-12',
    },
    significativo: true,
    requisitoLegalIds: [],
    riesgoOportunidadIds: [],
    fechaIdentificacion: '2026-03-12',
    responsableId: 'user-encargado',
  },
  {
    id: 'asp-3',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    procesoId: 'depto-operaciones',
    actividad: 'Almacenamiento de hipoclorito a granel',
    aspecto: 'Derrame por falla de estanque',
    tipoAspecto: 'contaminacion_suelo',
    impacto: 'Contaminacion de suelo y napa subterranea',
    condicionOperacion: 'emergencia',
    etapaCicloVida: 'produccion',
    evaluacion: {
      criterios: [
        { criterioId: 'crit-severidad', valor: 3 },
        { criterioId: 'crit-frecuencia', valor: 1 },
        { criterioId: 'crit-alcance', valor: 3 },
        { criterioId: 'crit-legal', valor: 3 },
      ],
      puntaje: 27,
      metodoId: 'producto',
      evaluadoPorId: 'user-admin-empresa',
      fecha: '2026-03-12',
      justificacion: 'Baja frecuencia pero consecuencia grave e irreversible.',
    },
    significativo: true,
    requisitoLegalIds: [],
    riesgoOportunidadIds: ['ryo-2'],
    fechaIdentificacion: '2026-03-12',
    responsableId: 'user-encargado',
  },
  {
    id: 'asp-4',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'plant-1',
    procesoId: 'depto-administracion',
    actividad: 'Uso de papel en oficinas',
    aspecto: 'Consumo de recursos forestales',
    tipoAspecto: 'consumo_energia',
    impacto: 'Presion sobre recursos naturales renovables',
    condicionOperacion: 'normal',
    etapaCicloVida: 'materias_primas',
    evaluacion: {
      criterios: [
        { criterioId: 'crit-severidad', valor: 1 },
        { criterioId: 'crit-frecuencia', valor: 3 },
        { criterioId: 'crit-alcance', valor: 1 },
        { criterioId: 'crit-legal', valor: 1 },
      ],
      puntaje: 3,
      metodoId: 'producto',
      evaluadoPorId: 'user-admin-empresa',
      fecha: '2026-03-12',
    },
    significativo: false,
    requisitoLegalIds: [],
    riesgoOportunidadIds: [],
    fechaIdentificacion: '2026-03-12',
  },
];
