# Sección E — Obligaciones / Declaraciones — Megaproyectos (S-13 a S-15)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-13 Listado de Obligaciones/Declaraciones**: tarjetas o tabla con nombre, período, estado general, N° tareas, próximo vencimiento, responsable. Filtros por sistema de declaración, planta, estado. Acción "Crear obligación" (puede nacer desde la Matriz o de forma libre — relación bidireccional).
- **S-14 Detalle de Obligación (Megaproyecto)**: encabezado con fechas y estado. Lista de tareas y subtareas (título, vencimiento, responsable, estado, evidencias). Acceso directo al historial de cambios del megaproyecto y de cada tarea. Botones: Agregar tarea, Generar Plan de Acción, Ver en Calendario/Gantt (misma entidad).
- **S-15 Detalle de Tarea/Subtarea**: estado, fecha de vencimiento, responsable, evidencias, forma de cumplimiento. Historial completo de cambios. Acciones: cambiar estado, adjuntar evidencia, generar plan de acción.
- Nota de diseño explícita: "El ticket es el mismo que se visualiza en Calendario y Gantt. Solo cambia la vista, no se duplica información."

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-14: separar Obligaciones/Declaraciones de la Matriz Legal manteniendo relación bidireccional.
- RF-15: modelar cada declaración periódica como megaproyecto (ej. "SIDREP Q3 2026") con tareas y subtareas.
- RF-16: cada tarea/subtarea tiene fecha de vencimiento, responsable, estado, evidencias y log de cambios.
- RF-17: las fechas de las tareas construyen automáticamente el Gantt/supercalendario (misma entidad, distinta vista) — Sección F.
- RF-18: evaluación de cumplimiento a nivel de artículo o tarea (SI/NO/NA, forma de cumplimiento, responsable, evidencias) — para Obligaciones el "estado" es de flujo (vigente/por vencer/vencida/sin evidencia), no de cumplimiento normativo SI/NO/NA como en Matriz Legal (ver gap).
- RF-19: obligación o tarea en incumplimiento puede generar planes de acción.
- RF-20: soporte para declaraciones discretas, periódicas y tipo proyecto/hitos.
- RF-21: historial completo de cambios (quién, cuándo, por qué, aprobación).

## Gaps o inconsistencias detectadas

- RF-18 mezcla dos modelos de estado distintos: el de Matriz Legal (SI/NO/NA, evaluación normativa por artículo) y el de Obligaciones (vigente/por_vencer/vencida/sin_evidencia, estado de flujo/plazo). El esquema `ObligationTask` en `packages/shared` usa el segundo modelo (`ObligationStatus`), consistente con cómo ya se usa en el Dashboard y en `mocks/obligations.ts` desde la iteración anterior. **No se introduce un campo SI/NO/NA en tareas** para no duplicar el concepto que ya vive en Matriz Legal — se documenta como decisión, no como pendiente.
- La relación bidireccional real (RF-09/RF-14: crear una obligación *desde* un artículo de la Matriz Legal, o promover una obligación libre *hacia* la Matriz) no se implementa en esta iteración: requiere decidir cómo se vincula un `Articulo` con una `Obligation` (campo `articuloOrigenId` u otro), lo cual no está definido en ningún RF con suficiente detalle. **Se deja como acción deshabilitada** ("Vincular a Matriz Legal — Próximamente") en el detalle de la obligación, evitando romper H1.
- "Ver en Calendario/Gantt" (mismo ticket, RF-17) no tiene ruta real porque la Sección F (Calendario/Gantt/Kanban) todavía no existe — se muestra deshabilitado con la misma convención "Próximamente".
- "Generar Plan de Acción" (RF-19) — **resuelto en la iteración de Sección F**: ahora se genera desde `TaskDetailModal` cuando la tarea está en `vencida`/`sin_evidencia`, usando la entidad `PlanAccion` de `packages/shared`.
- El historial de cambios (RF-21) se resuelve, igual que en Matriz Legal, como una sección visible dentro del detalle (no como ruta separada) — en esta iteración se deja un placeholder de "Historial" sin datos reales (no hay modelo de audit log en `packages/shared` todavía); se anota como pendiente transversal a varias secciones (D, E, G).

## Componentes Atomic Design necesarios

- Átomos: reutiliza `StatusBadge` (ya soporta vigente/por_vencer/vencida/sin_evidencia).
- Moléculas: reutiliza `FormField`, `FilterBar`, `Breadcrumbs`. Las filas de tarea van inline dentro del organismo de detalle (mismo criterio ya aplicado en `NormDetailView` de Matriz Legal: una fila de tabla usada en un solo lugar no se promueve a molécula — regla de Atomic Design del Paso 2).
- Organismos: `ObligationsListTable` (S-13, mismo patrón `overflow-x-auto` que `LegalMatrixTable` — H4), `ObligationDetailView` (S-14, header + lista de tareas), `TaskDetailModal` (S-15, sobre Radix Dialog — mismo patrón que `ArticleEvaluationModal`), `CreateObligationModal` (acción "Crear obligación" de S-13).
- Templates: ninguno nuevo.

## Datos de ejemplo necesarios (mock data)

- Ya cubierto por `mocks/obligations.ts` (creado en la iteración de Fundación): 7 obligaciones con tareas, cruzando los mismos tenant/plantas.
- Se agrega al menos una obligación con más de una tarea/subtarea para probar la lista de tareas en S-14 (hoy la mayoría tiene 1-2 tareas).

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — semáforo por obligación y por tarea; acciones no disponibles se muestran deshabilitadas con explicación, no ocultas ni rotas.
- [x] H2 Correspondencia con el mundo real — "SIDREP Q3 2026", "megaproyecto", nombres de sistema tal como en el funcional.
- [x] H3 Control y libertad — formulario de crear obligación con cancelar sin perder otras tareas ya cargadas.
- [x] H4 Consistencia — `ObligationsListTable` replica el patrón de `LegalMatrixTable`; `TaskDetailModal` replica el patrón de `ArticleEvaluationModal`.
- [x] H5 Prevención de errores — fecha de vencimiento de una tarea nueva no puede ser anterior a hoy, validado antes de guardar.
- [x] H6 Reconocer antes que recordar — breadcrumb Obligaciones > [nombre del megaproyecto].
- [x] H9 Recuperación de errores — mensajes humanos si falta un campo obligatorio al crear obligación o tarea.
