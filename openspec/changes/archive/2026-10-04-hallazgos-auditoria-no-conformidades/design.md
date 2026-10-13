# Design: Auditorías, Hallazgos y Registros de Mejora

Documento técnico de la propuesta [`proposal.md`](./proposal.md).
Evidencia en [`fuentes/entrevista-adclean-2026-07-29.md`](./fuentes/entrevista-adclean-2026-07-29.md).

---

## 1. Las cuatro capas y por qué son cuatro entidades

| Capa | Norma | Pregunta que responde | Entidad |
|---|---|---|---|
| Planificar | §9.2.2 | ¿Qué se audita, contra qué criterios, cuándo y con quién? | `Auditoria` + `SesionAuditoria` |
| Evaluar | ISO 19011 | ¿Se cumple cada requisito y con qué evidencia? | `ItemChecklist` |
| Concluir | ISO 19011 | ¿Qué se encontró? | `Hallazgo` |
| Tratar | §8.7 · §10.2 · §6.1 | ¿Qué se hace con lo que hay que mejorar? | `RegistroMejora` |

Fusionar planificación y tratamiento tiene un costo concreto: **no se puede
cerrar una auditoría sin cerrar todo lo que originó**, porque serían el mismo
objeto. En la realidad la auditoría se cierra con su informe, y el tratamiento
sigue su ciclo durante semanas o meses después.

Separar evaluación de conclusión permite algo que hoy no se puede: distinguir
un requisito que se evaluó y cumple de uno que nunca se alcanzó a mirar.

---

## 2. Modelo

### 2.1 `Auditoria`

```ts
Auditoria {
  id
  tenantId
  plantId
  codigo: string              // Formato configurable por tenant. Ej: "001/2026"
  tipo: 'interna' | 'externa'
  normaReferenciaIds: string[]  // "ISO 9001:2015"

  // Objetivo y alcance son campos distintos en el informe del cliente.
  objetivos: string[]         // Lista numerada, no un párrafo
  periodoAuditadoDesde: string
  periodoAuditadoHasta: string
  sitios: string[]            // "Oficina administrativa … / Operaciones y laboratorio …"

  // Rango, no fecha única: una auditoría se planifica con ventana.
  fechaInicioPlanificada: string
  fechaTerminoPlanificada: string
  fechaInicioReal?: string
  fechaTerminoReal?: string

  estado: 'planificada' | 'en_ejecucion' | 'ejecutada' | 'cerrada' | 'cancelada'

  // Criterios de auditoría (ISO 19011): contra qué se audita.
  normativaIds: string[]
  // Alcance: qué procesos entran. Referencia `Departamento.id` del Perfil
  // Empresa, que ya modela el departamento como proceso de §4.4 con tipo,
  // dueño, entradas y salidas.
  procesoIds: string[]

  auditorLiderId: string
  // No es una lista plana: cada auditor cubre procesos determinados.
  equipoAuditor: { auditorId: string; procesoIds: string[] }[]
  // Contraparte del auditado: representante legal, CFO, encargado del SGC…
  responsablesOrganizacion: { usuarioId: string; cargo: string }[]
  organismoAuditor?: string   // Solo externas

  // Metodología declarada (entrevistas, revisión documental, muestreo…).
  metodologia: string[]
  limitaciones?: string       // ISO 19011 pide declarar el alcance del muestreo

  informe?: InformeAuditoria
}
```

**Por qué `fechaInicioReal` separada de la planificada:** §9.2.2 pide mantener
el programa de auditorías. Si al reprogramar se sobrescribe la fecha original,
se pierde la evidencia de que el programa se desvió — que es justamente lo que
un certificador mira.

**Por qué `cancelada` es un estado y no un borrado:** una auditoría planificada
que no se ejecutó es información auditable. Borrarla oculta un incumplimiento
del programa.

**Por qué `limitaciones` es un campo y no una nota suelta:** el informe del
cliente lo trae como sección propia, y con razón — una auditoría por muestreo
que no lo declara está afirmando una cobertura que no tuvo.

### 2.2 `SesionAuditoria` — la agenda

Reemplaza el documento Word `PE2-R02 Plan Auditoría Interna`.

```ts
SesionAuditoria {
  id
  auditoriaId
  orden: number
  procesoId: string
  fecha: string
  horaInicio: string
  horaFin: string
  entrevistadoIds: string[]
  auditorId: string
  focoMetodo: string          // "Competencia, inducción, toma de conciencia"
  estado: 'planificada' | 'realizada' | 'no_realizada'
}
```

**Por qué merece entidad propia y no un campo de texto:** es lo que convierte
la auditoría en algo agendable. Sin sesiones no hay forma de que el sistema
avise a un entrevistado que lo auditan el jueves a las 11:30, que es
exactamente el tipo de cosa que hoy se resuelve por correo manual.

### 2.3 `NotaAuditoria` — el registro de campo del auditor

Reemplaza el formato Word `PE2-R08 Notas de Auditoría`. Se llena **por proceso
auditado**, no por auditoría.

```ts
NotaAuditoria {
  id
  auditoriaId
  procesoId
  responsableProcesoId: string
  cargoResponsable: string
  fecha: string
  auditorId: string
  sede: string
  entrevistadosAdicionalesIds: string[]

  clausulasAuditadas: string[]
  objetivoMuestreo: string
  periodoMuestraRevisada: string
  hizoSeguimientoHallazgosPrevios: boolean
}
```

**Por qué se modela y no se descarta como papeleo.** El propio informe del
cliente declara como limitación relevante que no se dispuso de la nota PE2-R08
del proceso de Producción, y que por eso la evidencia de ese proceso se
consolidó de otra forma. Es decir: la ausencia de este registro degrada la
auditoría y el cliente lo sabe. Un sistema que no lo tiene obliga a seguir
llevándolo en Word.

Es también lo que sostiene la trazabilidad entre la agenda y los hallazgos:
`SesionAuditoria` dice qué se iba a auditar, `NotaAuditoria` dice qué se
auditó realmente y sobre qué muestra.

### 2.4 `ItemChecklist` — la lista de verificación

Reemplaza el Excel `Checklist_ISO9001_*`.

```ts
ItemChecklist {
  id
  auditoriaId
  procesoId                   // El checklist es POR PROCESO, no por auditoría
  auditadoId?: string         // A quién se le aplicó
  fechaAplicacion?: string

  normativaId
  articuloId                  // Del Catálogo Normativo
  capitulo: string            // Agrupador: "4. Contexto de la organización"
  referencia: string          // Foto legible: "ISO 9001 §7.1.5"
  requisitoTextual: string    // Copiado de la norma al momento de auditar
  pregunta: string            // Pregunta de auditoría

  cumplimiento: 'cumple' | 'parcial' | 'no_cumple' | 'no_evaluado' | 'no_aplica'
  comentarios?: string
  evidencia?: string
  evidenciaUrls: string[]

  hallazgoId?: string         // Si derivó en hallazgo
}
```

**Sobre la escala.** El cliente usa 2/1/0. Se modela con nombres y no con
números porque el número invita a promediar, y el promedio de cumplimiento por
cláusula no significa nada: dos "parcial" no equivalen a un "cumple". El
porcentaje que el sistema muestre debe ser explícito sobre qué cuenta.

**`no_evaluado` y `no_aplica` son distintos y ambos hacen falta.** Un requisito
no aplicable sale del denominador de cobertura; uno no evaluado se queda dentro
y baja la cobertura. Confundirlos es la forma más fácil de inflar el indicador.

**Por qué se copia `requisitoTextual` en vez de solo referenciar el artículo:**
las normas cambian. Un checklist de 2026 debe seguir mostrando contra qué texto
se auditó, aunque el artículo se modifique después.

**Por qué `procesoId` y no solo `auditoriaId`:** el archivo del cliente se
llama `Checklist_ISO9001_08_Control_Calidad_2.xlsx` y su encabezado repite el
proceso. Una auditoría de 13 procesos son 13 checklists, cada uno con su
auditor, su auditado y su fecha. Colgarlos todos de la auditoría sin distinguir
el proceso hace imposible reconstruir quién evaluó qué.

### 2.5 `Hallazgo`

```ts
Hallazgo {
  id
  tenantId
  auditoriaId                 // Un hallazgo SIEMPRE pertenece a una auditoría
  itemChecklistId?            // Opcional: hay hallazgos transversales
  codigo: string              // Prefijo según clasificación: NC- / OBS- / OM-

  clasificacion: 'fortaleza' | 'conformidad' | 'no_conformidad' | 'observacion' | 'oportunidad_mejora'
  severidad: 'mayor' | 'menor' | null   // Solo si clasificacion === 'no_conformidad'

  requisitoAuditado: {
    normaId: string
    articuloId?: string
    referencia: string
  }

  procesoId: string
  descripcion: string         // Qué se observó
  evidenciaObjetiva: string   // En qué se sustenta
  evidenciaUrls: string[]
  riesgoImpacto?: string
  // La concordancia lleva justificación, no solo el código del otro hallazgo.
  concordanteCon: { hallazgoId: string; motivo: string }[]

  detectadoPorId: string
  fechaDeteccion: string
  responsableProcesoId: string
  plazoTratamiento?: string

  registroMejoraId?: string   // Se completa si derivó en tratamiento
}
```

**Aquí sí se mantiene el vínculo obligatorio con la auditoría**, al contrario
del `RegistroMejora`. Un hallazgo es, por definición de ISO 19011, el resultado
de evaluar evidencia contra criterios *en una auditoría*. Lo que se detecta
fuera de una auditoría no es un hallazgo: es directamente un registro de mejora.

**Regla de integridad:** `severidad` solo puede ser no nula cuando
`clasificacion === 'no_conformidad'`. Una conformidad "menor" no significa nada.

**Por qué `fortaleza` es una clasificación y no un adorno.** El resumen
ejecutivo del cliente cuenta ocho fortalezas y ningún "conforme". Una fortaleza
no es lo mismo que una conformidad: conformidad es "cumple el requisito",
fortaleza es "cumple notablemente y vale destacarlo". Se mantienen las dos
porque la cobertura de auditoría se mide con las conformidades —que son la
mayoría y nadie escribe una por una— y el informe se escribe con las
fortalezas, que son pocas y elegidas. Fusionarlas obliga a elegir entre medir
cobertura o poder redactar el informe.

**`concordanteCon` con motivo** sale del informe, que no se limita a enlazar:
explica *por qué* dos hallazgos son la misma brecha ("mismo tipo de brecha de
control de cambios, cl. 8.5.6, en un producto distinto"). Sin el motivo, el
enlace no sirve para decidir si se tratan juntos o por separado.

**Por qué `evidenciaObjetiva` es obligatoria y separada de `descripcion`:**
ISO 19011 distingue el hallazgo (la conclusión) de la evidencia de auditoría
(el hecho verificable que lo sustenta). Un hallazgo sin evidencia no es
defendible ante una apelación del auditado.

**`concordanteConIds`** sale directamente del informe del cliente, que agrupa
hallazgos que responden al mismo tipo de brecha. Sirve para no tratar cinco
veces la misma causa raíz.

### 2.6 `RegistroMejora` — la raíz

```ts
RegistroMejora {
  id
  tenantId
  plantId
  codigo: string

  // Eje 1: qué cláusula aplica.
  tipo: 'salida_no_conforme' | 'no_conformidad' | 'riesgo' | 'oportunidad' | 'reclamo'
  // Eje 2: cómo se detectó.
  origenDeteccion: 'interna' | 'externa' | 'analisis_foda' | 'auditoria_interna' | 'auditoria_externa'
  hallazgoId?: string         // Obligatorio si origenDeteccion es de auditoría

  fecha: string
  reportadoPorId: string
  descripcion: string
  procesoIds: string[]        // "Proceso Involucrado 1 y 2" del cliente, sin límite fijo
  adjuntosUrls: string[]

  // Solo si tipo === 'salida_no_conforme' (§8.7).
  producto?: {
    sku: string
    lote: string
    nombre: string
    cantidad: number
    unidad: string
  }

  // Solo si tipo === 'reclamo' (§9.1.2).
  reclamo?: {
    clienteId?: string
    clienteNombre: string
    canal: string
    fechaReclamo: string
  }

  // Solo si tipo === 'riesgo' | 'oportunidad' (§6.1).
  riesgoOportunidadId?: string

  estadoEtapa: 'registro' | 'analisis_causa' | 'correccion' | 'accion_correctiva' | 'seguimiento' | 'cerrado'

  responsables: {
    analisisCausaId: string
    accionCorrectivaId: string
    seguimientoId: string
  }

  etapas: {
    analisisCausa?: EtapaAnalisisCausa
    correccion?: EtapaCorreccion
    accionCorrectiva?: EtapaAccionCorrectiva
    seguimiento?: EtapaSeguimiento
  }

  cierre?: {
    fecha: string
    responsableId: string
    firmado: boolean
  }
}
```

**Los campos condicionales no son opcionales de verdad.** `producto` es
obligatorio cuando el tipo es salida no conforme, porque §8.7 exige identificar
qué salida se controló. La validación cruzada va en el schema, no en la
interfaz.

**`procesoIds` es lista y no dos campos fijos.** El cliente tiene
`Proceso Involucrado 1` y `2` porque Power Apps le hizo más fácil dos campos que
una relación. No hay razón normativa para el tope en dos.

### 2.7 Las etapas

```ts
EtapaAnalisisCausa {
  metodologiaId: string       // Del catálogo del tenant
  cincoPorques?: string[]     // Si la metodología es 5 Por Qué
  espinaPescado?: {           // Si es Diagrama de Pescado
    // Las cajas del cliente se ven sueltas, sin rótulo de categoría visible.
    // `categoria` queda opcional para admitir 6M sin obligarla — ver decisión
    // abierta #7.
    causas: { texto: string; categoria?: string; posicion?: { x: number; y: number } }[]
  }
  causaRaiz: string
  responsableEtapaId: string
  fechaEjecucion: string
  evidenciaUrls: string[]
}

EtapaCorreccion {            // §10.2.1 a): reaccionar y contener
  correccionInmediata: string
  fechaEjecucion: string
  evidencia: string
  responsableEtapaId: string
  evidenciaUrls: string[]
}

EtapaAccionCorrectiva {      // §10.2.1 b y c). El cliente la llama "Capa"
  severidad: string          // Del catálogo del tenant
  tipoAccion: 'correctiva' | 'preventiva'
  descripcionAccion: string
  evidenciaAccion: string
  planAccionId?: string
  fechaInicial: string
  fechaFinalizacion: string
  responsableEtapaId: string
  evidenciaUrls: string[]
}

EtapaSeguimiento {           // §10.2.1 d, e y f: verificar eficacia
  // Tri-estado, no booleano: `null` = sin responder, que no es "No".
  eficaz: boolean | null
  causaSeRepitio: boolean | null       // "…durante el periodo de seguimiento"
  cumplioProposito: boolean | null     // d) revisar la eficacia
  requiereActualizarRiesgos: boolean | null  // e) actualizar riesgos y oportunidades
  requiereCambiosSGC: boolean | null   // f) hacer cambios al sistema
  observaciones: string
  responsableEtapaId: string
  fechaVerificacion: string
  evidenciaUrls: string[]
}
```

**Las cuatro preguntas del seguimiento son literales del sistema del cliente**,
y las tres últimas son las sub-cláusulas d), e) y f) de §10.2.1. Se modelan
como campos separados y no como un texto libre porque cada una dispara algo
distinto: `requiereActualizarRiesgos` debería poder crear un registro de tipo
`riesgo`, y `requiereCambiosSGC` debería poder abrir un cambio documental.
Hoy no se implementa ese disparo, pero el dato queda listo para hacerlo.

**Por qué tri-estado y no booleano.** En la aplicación del cliente los cinco
campos son desplegables `Seleccione… / SI / NO`. Modelarlos como booleano
convierte "todavía no lo verifiqué" en "No", que en tres de las cuatro
preguntas es la respuesta *favorable* — o sea, el default silencioso cerraría
la verificación a favor. Es el tipo de error que vuelve inútil el registro
justo donde la norma pide rigor.

Consecuencia directa: el cierre exige `eficaz === true`, no `eficaz` truthy.

**Por qué `responsableEtapaId` está en cada etapa además de en `responsables`:**
son dos cosas distintas. `responsables` es a quién se le asignó al registrar;
`responsableEtapaId` es quién efectivamente la ejecutó. Cuando no coinciden,
eso mismo es información — significa que la asignación no funcionó.

---

## 3. Máquina de estados del Registro de Mejora

Orden por defecto, alineado a §10.2.1 (primero reaccionar, después analizar):

```
registro ──► correccion ──► analisis_causa ──► accion_correctiva ──► seguimiento ──► cerrado
                                                        ▲                  │
                                                        └── (no eficaz) ───┘
```

| Transición | Precondición |
|---|---|
| `registro → correccion` | Descripción, tipo, origen y responsables completos; campos condicionales del tipo válidos |
| `correccion → analisis_causa` | `correccionInmediata` no vacía |
| `analisis_causa → accion_correctiva` | `causaRaiz` no vacía y metodología completa según su forma |
| `accion_correctiva → seguimiento` | Existe acción con fechas; si hay `planAccionId`, su plan está cerrado |
| `seguimiento → cerrado` | `eficaz === true` y firma del responsable |
| `seguimiento → accion_correctiva` | `eficaz === false` |

**El orden es configuración de tenant, no constante.** El sistema del cliente
pone el análisis de causa antes de la corrección. Ambos órdenes son
defendibles; el de la norma es el que va por defecto. La configuración vive en
`ConfiguracionMejoras.ordenEtapas` y solo permite permutaciones válidas: el
registro siempre primero y el seguimiento siempre último.

**El bucle de reapertura no es un detalle:** es lo que distingue un sistema de
gestión real de un registro de tareas. Una acción correctiva que no funcionó
devuelve el registro a tratamiento, y ese ida y vuelta queda en el audit log.

**Los tipos `riesgo` y `oportunidad` no recorren todas las etapas.** No hay
"corrección inmediata" de una oportunidad. Para esos dos tipos el flujo se
reduce a `registro → accion_correctiva → seguimiento`, con `tipoAccion:
'preventiva'`. Es la única concesión al término "preventiva", y existe porque
§6.1 sí pide planificar acciones para riesgos y oportunidades.

---

## 4. Configuración por tenant

Ambienta es multi-tenant. Todo lo que la entrevista mostró como convención de
ADCLEAN y no como requisito normativo va acá:

```ts
ConfiguracionMejoras {
  tenantId
  escalaSeveridad: { valor: string; etiqueta: string; orden: number }[]
  metodologiasAnalisisCausa: { id: string; nombre: string; forma: 'cinco_porques' | 'espina_pescado' | 'texto_libre' }[]
  formatoCodigo: { prefijoPorTipo: Record<string, string>; patron: string }
  plazosPorDefectoDias: Record<EstadoEtapa, number>
  ordenEtapas: EstadoEtapa[]
  etiquetaAccionCorrectiva: string   // "Acciones Correctivas" | "CAPA" | …
}
```

**Por qué esto no es sobre-ingeniería.** Sin esta tabla, el segundo cliente que
entre obliga a un cambio de schema. Con ella, ADCLEAN se configura como un
preset y nadie más queda amarrado a su vocabulario. El costo es una tabla y una
pantalla de configuración; el costo de no tenerla es una migración por cliente.

---

## 5. Cobertura de auditoría

Al elegir las normas de una auditoría, el sistema despliega sus artículos como
ítems de checklist desde el Catálogo Normativo.

```
Cobertura = ítems evaluados / (ítems en alcance − ítems no aplicables)
```

Esto responde una pregunta que hoy el sistema no puede contestar: *"¿qué parte
de la norma alcanzamos a auditar?"*. Una auditoría con 20% de cobertura y cero
no conformidades no es una buena noticia — es una auditoría incompleta, y hoy
se ve idéntica a una completa sin hallazgos.

**Dependencia dura con el Catálogo Normativo.** El checklist necesita que las
normas estén descompuestas en artículos. Hoy el catálogo tiene el parsing
asistido especificado (RF-16) pero no implementado. Si el catálogo no entrega
artículos, el checklist se construye a mano y la cobertura se mide sobre lo que
el auditor cargó, no sobre la norma completa. Es una limitación real que hay que
decir en voz alta antes de prometer el indicador.

---

## 6. Informe de auditoría

```ts
InformeAuditoria {
  fechaEmision: string
  emitidoPorId: string
  resumenEjecutivo: {
    procesosAuditados: number
    fortalezas: number
    noConformidades: number
    observaciones: number
    oportunidadesMejora: number
  }
  conclusion: string
  tasaCierreCicloAnterior?: number

  // Matriz de resultados por proceso: una fila por proceso auditado.
  resultadosPorProceso: {
    procesoId: string
    clausulasAuditadas: string[]
    evidenciaClaveRevisada: string
    hallazgoIds: string[]
    clasificacion: string        // "Conforme con observaciones", "No conformidad"…
    conclusion: string           // Párrafo por proceso
  }[]

  distribucionIds: string[]
}
```

Los conteos son **derivados**, no capturados: salen de los hallazgos de la
auditoría. Guardarlos escritos a mano es la forma más rápida de que el informe
y el sistema digan cosas distintas.

**La matriz por proceso es la pieza que conecta el informe con la ejecución.**
Cada fila resume un proceso: contra qué cláusulas se lo auditó, qué evidencia
se miró, qué hallazgos salieron y cuál es la conclusión. Las tres primeras
columnas son derivables de `NotaAuditoria` e `ItemChecklist`; solo la
clasificación y la conclusión las escribe el auditor. Sin esta tabla el informe
es una lista de hallazgos sin decir cómo quedó cada proceso, que es
precisamente lo que el dueño de proceso quiere leer.

`tasaCierreCicloAnterior` sale del informe del cliente, que reporta cuántos
hallazgos de la auditoría anterior se cerraron. Es el indicador que conecta un
ciclo con el siguiente y hoy no existe en ningún lado.

---

## 7. Notificaciones

Requisito verbal de la entrevista: al guardar, llega correo a los responsables
con fecha límite.

| Evento | Destinatario | Contenido |
|---|---|---|
| Registro creado | Responsables de las tres etapas | Qué les toca y cuándo vence |
| Etapa avanzada | Responsable de la etapa entrante | Su plazo, calculado desde `plazosPorDefectoDias` |
| Plazo próximo a vencer | Responsable de la etapa actual | Escalamiento según RF-42 |
| Plazo vencido | Responsable + Admin Empresa | — |
| Sesión de auditoría agendada | Entrevistados y auditor | Fecha, hora, proceso y foco |
| Verificación no eficaz | Responsable de acción correctiva | Se reabre su etapa |

Esto es el primer consumidor real de `apps/worker` y de Resend (RF-41 a RF-45).
Los plazos vencidos exigen un job periódico, no solo eventos.

---

## 8. Migración desde el modelo actual

Los datos actuales son mocks, así que la migración es de **código**, no de
datos productivos. Aun así hay que definirla porque el audit log ya tiene
eventos con `entidadTipo: 'no_conformidad'`.

| Dato actual | Destino |
|---|---|
| `NonConformity` con `auditId` | `Hallazgo` (clasificación `no_conformidad`) + `RegistroMejora` con `origenDeteccion: 'auditoria_interna'` |
| `NonConformity` sin `auditId` | `RegistroMejora` con `origenDeteccion: 'interna'`, sin hallazgo |
| `criticidad: alta` | `severidad: mayor` |
| `criticidad: media` \| `baja` | `severidad: menor` (ver decisión abierta #2) |
| `cincoPorques` | `etapas.analisisCausa.cincoPorques`, con metodología `cinco_porques` |
| `cierre` | Se mantiene, pero ahora exige seguimiento eficaz previo |
| `Audit.fecha` | `fechaInicioPlanificada` y `fechaTerminoPlanificada` iguales |
| `Audit.procesos` (array de strings sueltos) | `procesoIds` referenciando `Departamento.id` |
| `OrigenPlanAccion: 'no_conformidad'` | Se agrega `'registro_mejora'`; el valor viejo se conserva por los planes ya creados |
| Audit log con `entidadTipo: 'no_conformidad'` | **Se conserva tal cual.** Los eventos históricos no se reescriben |

**Sobre el audit log:** reescribir eventos pasados violaría su inmutabilidad
(RNF-08). Se agregan los tipos nuevos y los eventos antiguos siguen diciendo
`no_conformidad`, que es lo que efectivamente ocurrió cuando se registraron.

---

## 9. Impacto en pantallas

| Pantalla | Cambio |
|---|---|
| S-20 Listado de auditorías | Agregar **crear auditoría**; mostrar rango, cobertura y estado |
| S-21 Detalle de auditoría | Agenda de sesiones, checklist y hallazgos; quitar acceso directo a NC |
| Nueva: Checklist de auditoría | Ítems por cláusula con evidencia y cumplimiento |
| Nueva: Informe de auditoría | Resumen ejecutivo derivado + fichas de hallazgo |
| S-24 Registrar hallazgo | Pasa a ser **Registrar mejora**: primero el tipo, después los campos condicionales |
| Nueva: Detalle de Registro de Mejora | **El flujo de etapas visible como stepper**, con lo anterior en solo lectura y la etapa actual editable |
| Nueva: Bandejas por etapa | Pendientes de análisis, de corrección, de acción correctiva y de seguimiento |
| S-06/S-07 Dashboard | Contadores por etapa y % de resolución |
| S-39/S-40 Reportes | Informe de auditoría como reporte; filtro por tipo y clasificación |
| Nueva: Configuración de mejoras | Catálogos del tenant (§4) |

**Sobre el detalle como stepper.** Es lo que pidió el cliente: al abrir un
registro se ve el flujo completo, no una etapa suelta. Su sistema ya lo hace —
muestra las etapas anteriores en solo lectura encima de la editable — y es la
diferencia principal contra tener cinco pantallas inconexas.

---

## 10. Lo que este diseño deliberadamente no resuelve

- **Programa anual de auditorías.** §9.2.2 pide un programa, no auditorías
  sueltas. Aquí cada auditoría es independiente. Es una carencia real pero de
  alcance mayor.
- **Auditorías de proveedores (segunda parte).** Necesita modelar al auditado
  como entidad, y eso toca el módulo de Gestores.
- **El disparo automático** desde `requiereActualizarRiesgos` y
  `requiereCambiosSGC` hacia los módulos de riesgos y de documentos. El dato se
  guarda; la automatización queda para después.
- **Firma electrónica con validez legal.** `firmado: boolean` es un registro de
  acto, no una firma criptográfica.
- **Control de documentos del SGC** (políticas, procedimientos, instructivos,
  obsoletos) que se vio en el SharePoint del cliente. Es §7.5 y es un módulo
  propio, no parte de auditorías.
