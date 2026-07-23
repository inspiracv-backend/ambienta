# Sección F — Calendario, Gantt y Kanban (S-16 a S-19)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-16 Calendario**: vista mensual/semanal de vencimientos y tareas (misma entidad que Obligaciones). Al hacer clic en un evento se abre el mismo detalle de tarea/obligación (ticket único). Toggle entre vista Calendario/Gantt/Kanban.
- **S-17 Vista Gantt**: construido automáticamente desde las fechas de las tareas de las declaraciones y planes de acción. Barras de color según estado y responsable. Click abre el detalle del ticket.
- **S-18 Kanban de Tareas**: columnas por estado o por responsable. Tarjetas con título, fecha y semáforo (ícono+color+texto).
- **S-19 Detalle de Plan de Acción**: detalle completo (tareas, responsables, fechas, evidencias, vínculo con el artículo o No Conformidad de origen). Historial de cambios.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-27: Calendario central con vencimientos, recordatorios y eventos generados desde las tareas de declaraciones y planes de acción.
- RF-28: vista Gantt construida automáticamente (misma entidad ticket que Obligaciones).
- RF-29: vista de tareas por persona/requerimiento (Kanban).
- RF-19: obligación o artículo en incumplimiento puede generar uno o más Planes de Acción.

## Gaps o inconsistencias detectadas

- **`PlanDeAccion` no existía en `packages/shared`** — quedó documentado como pendiente en `seccion-c-dashboard.md`, `seccion-d-matriz-legal.md` y `seccion-e-obligaciones.md` (los botones "Generar Plan de Acción" estaban deshabilitados con "Próximamente"). Como S-19 es parte formal de esta sección, **se modela ahora**: `PlanAccionSchema` en `packages/shared/src/schemas/plan-accion.ts`, con un origen genérico (`articulo` | `tarea_obligacion` | `no_conformidad` + id + etiqueta) en vez de una FK tipada por entidad, porque el origen puede venir de tres módulos distintos (D, E, G) y solo dos existen hoy. Los botones "Generar Plan de Acción" en Matriz Legal y Obligaciones **se habilitan** en esta iteración.
- No existe una pantalla de listado propio de Planes de Acción en el Esquema de Pantallas (no aparece como sección de la barra de navegación global) — se accede contextualmente desde donde se generó (artículo o tarea) y desde la vista Kanban/Gantt (que sí puede incluirlos junto a las tareas de obligación, per RF-27/28 "eventos generados desde... planes de acción"). **No se agrega ítem de sidebar para Planes de Acción.**
- El Kanban (S-18) dice "columnas por estado o por responsable" sin fijar cuáles estados — se usan directamente los 4 estados ya existentes de `ObligationStatus` (vigente/por_vencer/vencida/sin_evidencia) en vez de inventar una taxonomía paralela tipo "Por hacer/En progreso/Completado", para no violar H4 (mismo semáforo en toda la plataforma).
- La Vista Gantt (S-17) se implementa como una lista de barras horizontales proporcionales a la fecha dentro del rango visible (sin librería de terceros ni drag-and-drop) — suficiente para representar "construido automáticamente desde las fechas" sin agregar una dependencia pesada no solicitada por ningún RF.
- El historial de cambios (RF-21, mencionado también en D y E) sigue sin modelo de audit log real — se mantiene como gap transversal, ahora anotado también aquí para S-19.
- `GanttView` usa el mismo patrón `overflow-x-auto` que las tablas de Matriz Legal/Obligaciones en mobile (mismo gap ya documentado, mismo criterio de solución — H4).

## Componentes Atomic Design necesarios

- Átomos: reutiliza `StatusBadge`.
- Moléculas: reutiliza `Breadcrumbs`, `FormField`.
- Organismos: `ViewToggle` (Calendario/Gantt/Kanban), `CalendarMonthView` (S-16), `GanttView` (S-17), `KanbanBoard` (S-18), `PlanAccionDetailView` (S-19). Todos consumen el mismo `ObligationTask[]` — ningún organismo nuevo duplica el modelo de datos.
- Templates: ninguno nuevo.

## Datos de ejemplo necesarios (mock data)

- Reutiliza `mocks/obligations.ts` (ya existente) — no se necesitan mocks nuevos para Calendario/Gantt/Kanban porque son vistas alternativas del mismo dato.
- Se agrega un Plan de Acción mock de ejemplo en un nuevo `mocks/action-plans.ts`, originado desde el Art. 10 "No cumple" de `norm-1` (Matriz Legal), para que S-19 tenga contenido representativo desde el primer render.

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — el ticket muestra el mismo semáforo en las 3 vistas (Calendario/Gantt/Kanban); el toggle deja claro en qué vista se está.
- [x] H2 Correspondencia con el mundo real — "Plan de Acción", nombres de sistema y estado sin sinónimos inventados.
- [x] H4 Consistencia — **la nota de diseño "ticket único" se cumple literalmente**: el mismo `TaskDetailModal` de Obligaciones (Sección E) se reutiliza sin duplicar al hacer clic en un evento del Calendario, una barra del Gantt o una tarjeta del Kanban.
- [x] H6 Reconocer antes que recordar — el toggle de vista permanece visible y el mes/rango actual se indica siempre.
- [x] H7 Flexibilidad y eficiencia — Kanban favorece al rol operativo (Usuario Interno) que gestiona tareas día a día; Gantt favorece la planificación de Admin Empresa.
- [x] H8 Estética minimalista — Gantt y Kanban muestran solo lo necesario para decidir (título, fecha, estado, responsable), sin densidad extra.
