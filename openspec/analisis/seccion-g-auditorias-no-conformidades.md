# Sección G — Auditorías y No Conformidades (S-20 a S-24)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-20 Listado de Auditorías**: lista de planificaciones de revisión (internas/externas) con filtros por estado y planta.
- **S-21 Detalle de Auditoría**: procesos, departamentos, normativas asociadas y hallazgos generados desde ella.
- **S-22 Listado de No Conformidades**: filtros por estado, planta y criticidad. Semáforo + fecha de detección + responsable.
- **S-23 Detalle de No Conformidad + 5 ¿Por qué?**: datos del hallazgo, análisis de causa raíz (5 ¿Por qué?), planes de acción asociados, timeline de seguimiento y cierre (firma/responsable/fecha), historial de cambios.
- **S-24 Crear/Registrar Hallazgo**: formulario simple y rápido, pensado también para uso en terreno (móvil).

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-34: registro de hallazgos mediante formulario.
- RF-35: análisis de causas raíz con metodología de los 5 ¿Por qué?.
- RF-36: generación de informes de hallazgo con seguimiento de acciones correctivas.
- RF-37: cierre de no conformidades con firma del responsable y registro de fecha.
- RF-38: pantalla resumen de no conformidades activas (estados, normativas asociadas).
- RF-39: clasificación de auditorías como internas o externas.
- RF-40: vinculación de procesos, departamentos y normativas a las auditorías.
- RF-41: toda NC debe poder generar automáticamente un Plan de Acción y quedar vinculada a la obligación o artículo de norma correspondiente.

## Gaps o inconsistencias detectadas

- RF-41 dice que la NC puede vincularse "a la obligación o artículo de norma correspondiente" además de generar el Plan de Acción — el vínculo NC → artículo/obligación de origen no está definido con más detalle en ningún RF. Se implementa el Plan de Acción (ya soportado por `PlanAccion.origenTipo === 'no_conformidad'`, Sección F) pero **no** un selector de artículo/obligación de origen para la NC misma — se documenta como gap, análogo al ya anotado en Matriz Legal/Obligaciones sobre la relación bidireccional.
- "Informes de hallazgo con seguimiento" (RF-36) no tiene una pantalla propia en el Esquema de Pantallas — se resuelve como parte del detalle de NC (S-23), no como reporte exportable (eso pertenece a la Sección M, Reportes, aún no implementada).
- El "timeline de seguimiento" (S-23) y el "historial de cambios" (mencionado también en D, E, F) siguen sin modelo de audit log real — se implementa solo el campo de **cierre puntual** (`cierre: { fecha, responsableId, firmada }`) que pide explícitamente RF-37, no un timeline completo de eventos.
- S-24 pide explícitamente prioridad mobile ("pensado también para uso en terreno") — se implementa el formulario con el mismo patrón de Sección A (validación inline, mobile-first) sin campos que dependan de mouse/hover.

## Componentes Atomic Design necesarios

- Átomos: reutiliza `StatusBadge` (nuevo mapeo para estados de auditoría/NC — ver decisión abajo).
- Moléculas: reutiliza `FormField`, `FilterBar`, `Breadcrumbs`.
- Organismos: `AuditsListTable` (S-20), `AuditDetailView` (S-21), `NonConformitiesListTable` (S-22), `NonConformityDetailView` (S-23, incluye 5 ¿Por qué? y cierre), `RegisterFindingForm` (S-24, standalone mobile-first).
- Templates: ninguno nuevo.

## Decisión: mapeo de estados al semáforo existente

`Audit.estado` (planificada/en_curso/cerrada) y `NonConformity.estado` (abierta/en_tratamiento/cerrada) no coinciden literalmente con los estados de `SemaforoStatus` ya existentes (cumple/parcial/no_cumple/etc.). Se añade un mapeo local en `lib/audit-status.ts` que traduce estos estados a un `SemaforoStatus` visual (ej. `abierta`→`no_cumple`, `en_tratamiento`→`parcial`, `cerrada`→`cumple`) **sin** agregar nuevos valores al átomo `StatusBadge` — mantiene H4 (un solo átomo de semáforo) sin forzar que Audit/NC hereden literalmente los estados de Obligación, que representan un concepto distinto (plazo vs. hallazgo).

## Datos de ejemplo necesarios (mock data)

- Ampliado `mocks/audits.ts`: 3 auditorías (planificada, cerrada, en curso) y 3 No Conformidades (abierta sin 5-porqués, en tratamiento con 2 de 5 porqués, cerrada con los 5 completos y cierre firmado) — cruzando las mismas plantas de `mocks/tenants.ts`.

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — semáforo por auditoría y por NC; contador de NC activas ya visible desde el Dashboard (Sección C).
- [x] H2 Correspondencia con el mundo real — "Auditoría", "No Conformidad", "5 ¿Por qué?" tal como los usa el equipo de calidad/ambiental, no jerga de software.
- [x] H3 Control y libertad — 5 ¿Por qué? se completa de forma iterativa (no todos los campos obligatorios de una vez), cancelar el formulario de hallazgo no pierde otras NC.
- [x] H4 Consistencia — mismo patrón `overflow-x-auto` + filtros que Matriz Legal/Obligaciones; mismo `PlanAccion` de la Sección F para NC en incumplimiento.
- [x] H5 Prevención de errores — cierre de NC exige firma explícita (checkbox) antes de permitir marcar como cerrada.
- [x] H6 Reconocer antes que recordar — breadcrumb Auditorías > [nombre] y No Conformidades > [hallazgo].
- [x] H7 Flexibilidad y eficiencia — S-24 optimizado para uso rápido en terreno (mobile-first, mínimos campos obligatorios).
- [x] H9 Recuperación de errores — mensajes humanos si falta un campo obligatorio al registrar hallazgo o cerrar NC.
