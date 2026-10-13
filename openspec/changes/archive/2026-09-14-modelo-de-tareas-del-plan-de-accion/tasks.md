## 1. Base de datos

- [x] 1.1 Crear `db/31_tareas_del_plan_de_accion.sql` (**31 y no 23**: el 23 ya era `normativa_transversal` cuando se implementó), idempotente: `tasks.action_plan_id` nulable con clave foránea a `action_plans(id)`
- [x] 1.2 Agregar el CHECK de padre único: como máximo uno entre `obligation_id` y `action_plan_id`, permitiendo que los dos sean nulos
- [x] 1.3 Comprobar antes de crear el CHECK que ninguna fila lo violaría, y fallar con un mensaje claro en vez de a la mitad
- [x] 1.4 Índice parcial `ix_tasks_action_plan (action_plan_id) WHERE deleted_at IS NULL`, en la forma de `ix_tasks_obligation`
- [x] 1.5 Dejar escrito en la migración **por qué NO declara política RLS ni GRANT**: agrega una columna a una tabla que ya los tiene, y duplicarlos sería el error contrario
- [x] 1.6 Registrar la migración en los **cinco** lugares: `docker-compose.yml`, `docker-compose.prod.yml`, `db/run.sh`, `db/README.md` y el bucle de `.github/workflows/ci.yml`
- [x] 1.7 Verificar que el bucle de CI la incluye ejecutándolo contra una base recién creada, no solo leyéndolo — hecho el 14-sep leyendo la lista del propio `ci.yml` (31 scripts) sobre una base vacía

## 2. API — modelo y esquemas

- [x] 2.1 `Task.action_plan_id` en `app/models/obligations.py`
- [x] 2.2 `TaskCreate` acepta `action_plan_id`; los `Read` lo devuelven
- [x] 2.3 Excepción de dominio para el padre doble, traducida a **422** con mensaje legible
- [x] 2.4 Comprobar el padre único en el servicio **antes** de escribir, para no depender del error de restricción

## 3. API — rutas

- [x] 3.1 `GET /audits/action-plans/{id}/tasks` — listar. **Sin paginación**: un plan tiene decenas de tareas, no miles; ordenado por creación
- [x] 3.2 `POST /audits/action-plans/{id}/tasks` — crear
- [x] 3.3 `GET`, `PATCH`, `DELETE` sobre `/audits/action-plans/tasks/{task_id}`, en paralelo a las de obligación
- [x] 3.4 Comprobar que la familia de permisos derivada es `action_plan` y **no** hace falta un permiso nuevo
- [x] 3.5 Declarar el motivo en `SIN_CRUD_COMPLETO` o en los sufijos de acción si la guarda de cobertura lo pide

## 4. Pruebas de la API

- [x] 4.1 Crear una tarea en un plan y comprobar que **queda en la base**, leyéndola desde otra conexión
- [x] 4.2 Una tarea con obligación **y** plan se rechaza con 422
- [x] 4.3 Una tarea sin ningún padre se acepta — la otra mitad, sin la cual la regla sería «exactamente uno»
- [x] 4.4 Dos tareas del mismo plan con responsables distintos
- [x] 4.5 «Lo que le toca a una persona» devuelve tareas de dos planes distintos y **no** las de otra persona
- [x] 4.6 Aislamiento contra la base real: la empresa B no ve las tareas del plan de la A
- [x] 4.7 La empresa B no puede crear una tarea en el plan de la A
- [x] 4.8 Un plan inventado y uno ajeno responden **idéntico**: mismo código y mismo mensaje
- [x] 4.9 Retirar el plan no borra sus tareas
- [x] 4.10 Mutar cada regla y confirmar que la prueba correspondiente cae; informar solo con la línea base en verde

## 5. Frontend

- [x] 5.1 Las tareas se leen de la API — **en la ficha del plan (`lib/tareas-del-plan.ts`), no en el store del listado**: cargarlas ahí sería una petición por plan. El listado conserva `tareas: []` y su mapper lo dice
- [x] 5.2 Mapear el vocabulario de estados **desde la base hacia la pantalla**, no al revés, y mostrar crudo lo que no reconozca
- [x] 5.3 `toggleTarea` escribe contra la API, espera la respuesta y **revierte la vista si el servidor rechaza**
- [x] 5.4 La pantalla dice cuando la carga falló, en vez de mostrar una lista vacía que se lee como «no hay tareas» (#208)
- [x] 5.5 Pruebas del store: lo que se manda, lo que se lee, y el estado tras un rechazo
- [x] 5.6 Mutar el store y confirmar que las pruebas caen

## 6. Cierre

- [x] 6.1 Suite completa de API y de navegador en verde, con los números medidos
- [x] 6.2 `ruff`, `tsc --noEmit` y `next lint` limpios
- [x] 6.3 Actualizar la entrada de estado de `CLAUDE.md` con lo medido, no con lo esperado
- [x] 6.4 Archivar el cambio con `/opsx:archive` para que `openspec/specs/` refleje el sistema real (14-sep)

## Medido al cerrar (14-sep-2026)

- API: 1450 pasan, 12 se omiten; `test_tareas_del_plan.py` 14 pruebas. Cuatro
  mutaciones (plan sin comprobar, responsable sin validar, `completed_at`,
  tareas de obligación por la ruta del plan) caen cada una en su prueba.
- Web: 772 pasan; `TareasDelPlanPanel.test.tsx` 6 pruebas, y quitar la
  reversión hace caer la suya.
- `ruff`, `tsc --noEmit` y `next lint` limpios.
- Además de lo planeado: un formulario para **agregar** tareas en la ficha. Sin
  él, las tareas solo existían si alguien las creaba por fuera de la pantalla.
