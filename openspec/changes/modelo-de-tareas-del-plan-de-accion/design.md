## Context

Ver `proposal.md` — Why.

Lo que hace falta saber del estado actual, medido contra la base:

- **`tasks` ya existe y es el ticket compartido.** Tiene `assignee_user_id`,
  `status`, `due_at`, `progress_percent`, `parent_task_id` y el índice parcial
  `ix_tasks_assignee (assignee_user_id, status) WHERE deleted_at IS NULL` —
  exactamente la consulta «lo que le toca a esta persona». La issue #112
  («Ticket único compartido entre Obligaciones, Calendario y Gantt») está
  cerrada sobre esta tabla.
- **`tasks.obligation_id` ya es nulable**, así que una tarea sin obligación es
  representable en el esquema. Lo que no existe es el camino para crearla: la
  única ruta es `POST /obligations/{id}/tasks`.
- **`action_plans` no tiene nada de tareas**, y `ActionPlanUpdate` expone ocho
  campos, ninguno de ellos una lista.
- Los CHECK vigentes de `tasks`:
  - `task_type ∈ {task, milestone, approval, evidence_request, support_ticket}`
  - `status ∈ {todo, in_progress, blocked, review, done, cancelled}`
  - `priority ∈ {low, medium, high, critical}`
  - `progress_percent` entre 0 y 100

## Goals / Non-Goals

**Goals:**
- Que una tarea de un plan sea **el mismo registro** que ya leen Calendario y
  Gantt, sin que esos módulos cambien.
- Que la consulta «qué le toca a esta persona» siga siendo **una sola**.
- Que el aislamiento entre empresas se apoye en lo que ya existe (RLS sobre
  `tasks`), no en una política nueva que haya que mantener coherente.

**Non-Goals:**
- **No se tocan las cinco etapas del Registro de Mejora** (#38, #43). Este
  cambio da el soporte de tareas con responsable; qué son las cinco etapas y
  cómo se nombran es otra decisión y otra issue.
- **No se cambia el vocabulario de estados.** El frontend usa nombres propios y
  manda la base, igual que en `lib/iso-vocabulario.ts`. Traducir aquí crearía un
  tercer vocabulario.
- No se agrega verificación de eficacia (#39) ni informe (#42).

## Decisions

### Una columna en `tasks`, no una tabla nueva

**Decidido con el usuario.** La decisión del equipo (13-ago-2026) fue *«tabla
propia, no una lista dentro del plan»*, y una columna en `tasks` la cumple:
sigue siendo una tabla con sus endpoints, no un `jsonb` embebido.

La alternativa —`action_plan_tasks`— se descartó porque produce **dos conceptos
de tarea**:

| | `tasks` + columna | tabla nueva |
|---|---|---|
| Calendario y Gantt ven las del plan | sí, sin cambios | no, hasta hacer trabajo extra |
| «Mis tareas» | una consulta | dos, y hay que unirlas |
| Vocabulario de estados | uno | dos, que se desincronizan |
| Contradice #112 (cerrada) | no | sí |

### El padre único se impone en la base, no solo en el servicio

Un `CHECK` sobre `(obligation_id, action_plan_id)` que admita **como máximo
uno**. Va en Postgres porque un `UPDATE` a mano tiene que respetarlo igual; el
servicio lo comprueba antes solo para responder un 422 legible en vez de un
error de restricción, que se lee como una falla del sistema y no como un dato
mal puesto.

Se permite que **los dos sean nulos**: una tarea suelta es legítima. La
restricción es «no dos», no «exactamente uno» — a diferencia de
`ck_crm_activities_un_solo_padre`, donde una actividad sin padre no aparecería
en ninguna ficha y por eso sí se exige uno.

### La migración agrega una columna, así que no declara RLS ni GRANT

`db/01_schema.sql` corre su bucle de políticas y su `GRANT ON ALL TABLES` una
sola vez, así que **una tabla nacida en una migración no los hereda**. Esa
trampa no aplica aquí: `tasks` ya existe con su política y sus permisos, y una
columna nueva queda cubierta por ambos.

Conviene decirlo explícitamente en la migración para que nadie «arregle» la
omisión agregando una política duplicada.

### Índice parcial, no total

`CREATE INDEX ... ON tasks (action_plan_id) WHERE deleted_at IS NULL`, en la
misma forma que `ix_tasks_obligation`. Las consultas siempre excluyen las
retiradas, así que indexarlas es espacio que no se usa.

### Las rutas van anidadas bajo el plan

`/audits/action-plans/{id}/tasks`, en paralelo a
`/obligations/{id}/tasks`. Dos razones:

1. El identificador del plan viaja en la ruta y no en el cuerpo, así que **no
   hace falta `validar_visible` para él**: si RLS no ve el plan, el 404 llega
   antes. Una clave foránea en el cuerpo sí exigiría comprobarla, porque las
   claves foráneas no pasan por RLS.
2. La familia de permisos se deriva de la raíz de la ruta, y `action_plan` ya
   existe en el catálogo. Un permiso nuevo que nadie tenga es un 403 para todo
   el mundo, y eso ya pasó una vez en este repositorio.

## Risks / Trade-offs

**El CHECK podría rechazar filas existentes.** Hoy es imposible —la columna no
existe, así que ninguna fila puede tener las dos referencias— pero la migración
debe comprobarlo igual antes de crear la restricción. Una migración que falla a
la mitad deja la base en un estado que nadie eligió.

**`tasks` se vuelve más polivalente.** Ya servía a obligaciones y ahora también
a planes de acción; el CHECK de padre único es lo que evita que eso degenere en
una tabla que significa cualquier cosa. Si mañana aparece un tercer padre, el
CHECK hay que ampliarlo a mano — es deliberado: obliga a decidir en vez de
dejar que la tabla acumule referencias en silencio.

**El frontend habla otro vocabulario de estados.** `toggleTarea` piensa en
completada/no completada y la base tiene seis estados. El mapeo vive en el
frontend y manda la base; el riesgo es que alguien lo invierta «para
simplificar», que es exactamente cómo se llegó a que
`environmental_aspects.significance` guardara estados de cumplimiento.
