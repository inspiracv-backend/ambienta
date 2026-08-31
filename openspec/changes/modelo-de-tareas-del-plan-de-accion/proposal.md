## Why

Un plan de acción no tiene dónde guardar sus tareas. `plan-accion-store` arma
cada plan con `tareas: []` escrito a mano, y `ActionPlanUpdate` —los ocho campos
que la API acepta— **no tiene ninguno** donde ponerlas. Marcar una tarea como
hecha se ve en pantalla y se pierde al recargar.

Eso deja RF-97 sin cumplir: pide cinco etapas **con responsable por etapa**, y
hoy no hay forma de asignarle una etapa a una persona ni de preguntar qué le
toca a alguien entre varios planes.

Importa ahora porque el Registro de Mejora (épica #27) se apoya entero en esto:
sin tareas persistidas no hay etapas, sin etapas no hay verificación de eficacia
(#39) ni informe con tasa de cierre (#42).

## What Changes

**Las tareas del plan de acción son el mismo ticket que ya usan Obligaciones,
Calendario y Gantt.** Se agrega `action_plan_id` a `tasks` en vez de crear una
tabla paralela.

La decisión del equipo (13-ago-2026) fue *«tabla propia con sus endpoints, no
una lista dentro del plan»*, y esto la cumple: `tasks` es una tabla, no un
`jsonb`. Lo que la decisión descartaba era guardarlas embebidas en el plan.

Crear `action_plan_tasks` aparte contradiría #112 —«Ticket único compartido entre
Obligaciones, Calendario y Gantt», ya cerrada— y dejaría dos conceptos de tarea:
el Calendario y el Gantt no verían las del plan, «mis tareas» necesitaría dos
consultas, y habría dos vocabularios de estado que mantener coherentes a mano.
Este repositorio ya tiene la lección de que dos definiciones de lo mismo se
desincronizan solas.

Cambios concretos:

- **Migración `db/23_tareas_del_plan_de_accion.sql`**, idempotente: agrega
  `tasks.action_plan_id` con su clave foránea e índice parcial.
- **`tasks` deja de colgar solo de una obligación.** Hoy `obligation_id` ya es
  nulable, pero la única ruta que crea tareas es
  `POST /obligations/{id}/tasks`: una tarea sin obligación **no se puede crear
  desde la API**. Se agrega el camino por plan de acción.
- **Endpoints anidados bajo el plan**, en paralelo a los de obligación:
  listar, crear, ver, editar y retirar.
- **Una tarea cuelga de una cosa o de ninguna, nunca de dos.** Un CHECK impide
  que la misma tarea sea a la vez de una obligación y de un plan — si no, la
  misma aparecería dos veces en «mis tareas» y contaría doble en la tasa de
  cierre.
- **`toggleTarea` llega a la base.** Hoy solo cambia el estado en memoria.
- **NO se toca el vocabulario de estados.** `tasks.status` ya admite
  `todo | in_progress | blocked | review | done | cancelled`; el frontend usa
  otros nombres y **manda la base**, como en `lib/iso-vocabulario.ts`.

No hay cambios **BREAKING**: `action_plan_id` es nulable y ninguna ruta existente
cambia de forma.

## Capabilities

### New Capabilities
- `plan-de-accion`: qué es una tarea de un plan de acción, de qué puede colgar,
  quién la tiene asignada, y cómo se consulta lo que le toca a una persona a
  través de varios planes.

### Modified Capabilities
<!-- Ninguna. `contrato-de-recursos`, `dashboard` y `normativa-aplicable` son los
     specs vivos y ninguno describe requisitos sobre tareas ni sobre planes de
     acción, así que no hay comportamiento declarado que cambie. -->

## Impact

**Base de datos**
- `db/23_tareas_del_plan_de_accion.sql` (nueva).
- Registrarla en los **cinco** lugares que deben coincidir:
  `docker-compose.yml`, `docker-compose.prod.yml`, `db/run.sh`, `db/README.md`
  y **el bucle de `.github/workflows/ci.yml`**. La issue #169 solo menciona
  cuatro y omite el de CI, que es justamente el que se olvida: no rompe nada en
  local —donde Docker ya aplicó el archivo— y hace fallar CI con
  `column ... does not exist`, que se lee como un error del código.
- La migración **agrega una columna a una tabla existente**, así que no necesita
  declarar política RLS ni GRANT propios: `tasks` ya los tiene. Esa advertencia
  aplica a tablas nuevas, y aquí no se crea ninguna.

**API**
- `app/models/obligations.py`: `Task.action_plan_id`.
- `app/schemas/`: `TaskCreate` acepta el plan; los `Read` lo devuelven.
- `app/routers/audits.py`: cinco rutas nuevas bajo `/audits/action-plans/{id}/tasks`.
- `app/permisos_de_rutas.py`: las rutas nuevas caen bajo la familia
  `action_plan`, que ya existe; no hace falta un permiso nuevo — y uno nuevo que
  nadie tenga sería un 403 para todos.

**Frontend**
- `lib/plan-accion-store.tsx`: dejar de escribir `tareas: []`, mapear las de la
  API y hacer que `toggleTarea` escriba.
- `components/organisms/PlanAccionDetailView`.

**Riesgo**
- El CHECK de padre único puede rechazar filas ya existentes si alguna tuviera
  las dos referencias. Hoy es imposible —`action_plan_id` no existe— pero la
  migración debe comprobarlo igual antes de crear la restricción, en vez de
  fallar a medias.
