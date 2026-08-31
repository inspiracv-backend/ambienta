## 1. Base de datos

- [ ] 1.1 Crear `db/23_tareas_del_plan_de_accion.sql`, idempotente: `tasks.action_plan_id` nulable con clave foránea a `action_plans(id)`
- [ ] 1.2 Agregar el CHECK de padre único: como máximo uno entre `obligation_id` y `action_plan_id`, permitiendo que los dos sean nulos
- [ ] 1.3 Comprobar antes de crear el CHECK que ninguna fila lo violaría, y fallar con un mensaje claro en vez de a la mitad
- [ ] 1.4 Índice parcial `ix_tasks_action_plan (action_plan_id) WHERE deleted_at IS NULL`, en la forma de `ix_tasks_obligation`
- [ ] 1.5 Dejar escrito en la migración **por qué NO declara política RLS ni GRANT**: agrega una columna a una tabla que ya los tiene, y duplicarlos sería el error contrario
- [ ] 1.6 Registrar la migración en los **cinco** lugares: `docker-compose.yml`, `docker-compose.prod.yml`, `db/run.sh`, `db/README.md` y el bucle de `.github/workflows/ci.yml`
- [ ] 1.7 Verificar que el bucle de CI la incluye ejecutándolo contra una base recién creada, no solo leyéndolo

## 2. API — modelo y esquemas

- [ ] 2.1 `Task.action_plan_id` en `app/models/obligations.py`
- [ ] 2.2 `TaskCreate` acepta `action_plan_id`; los `Read` lo devuelven
- [ ] 2.3 Excepción de dominio para el padre doble, traducida a **422** con mensaje legible
- [ ] 2.4 Comprobar el padre único en el servicio **antes** de escribir, para no depender del error de restricción

## 3. API — rutas

- [ ] 3.1 `GET /audits/action-plans/{id}/tasks` — listar, con la paginación acotada de #167
- [ ] 3.2 `POST /audits/action-plans/{id}/tasks` — crear
- [ ] 3.3 `GET`, `PATCH`, `DELETE` sobre `/audits/action-plans/tasks/{task_id}`, en paralelo a las de obligación
- [ ] 3.4 Comprobar que la familia de permisos derivada es `action_plan` y **no** hace falta un permiso nuevo
- [ ] 3.5 Declarar el motivo en `SIN_CRUD_COMPLETO` o en los sufijos de acción si la guarda de cobertura lo pide

## 4. Pruebas de la API

- [ ] 4.1 Crear una tarea en un plan y comprobar que **queda en la base**, leyéndola desde otra conexión
- [ ] 4.2 Una tarea con obligación **y** plan se rechaza con 422
- [ ] 4.3 Una tarea sin ningún padre se acepta — la otra mitad, sin la cual la regla sería «exactamente uno»
- [ ] 4.4 Dos tareas del mismo plan con responsables distintos
- [ ] 4.5 «Lo que le toca a una persona» devuelve tareas de dos planes distintos y **no** las de otra persona
- [ ] 4.6 Aislamiento contra la base real: la empresa B no ve las tareas del plan de la A
- [ ] 4.7 La empresa B no puede crear una tarea en el plan de la A
- [ ] 4.8 Un plan inventado y uno ajeno responden **idéntico**: mismo código y mismo mensaje
- [ ] 4.9 Retirar el plan no borra sus tareas
- [ ] 4.10 Mutar cada regla y confirmar que la prueba correspondiente cae; informar solo con la línea base en verde

## 5. Frontend

- [ ] 5.1 `plan-accion-store` deja de escribir `tareas: []` y mapea las de la API
- [ ] 5.2 Mapear el vocabulario de estados **desde la base hacia la pantalla**, no al revés, y mostrar crudo lo que no reconozca
- [ ] 5.3 `toggleTarea` escribe contra la API, espera la respuesta y **revierte la vista si el servidor rechaza**
- [ ] 5.4 La pantalla dice cuando la carga falló, en vez de mostrar una lista vacía que se lee como «no hay tareas» (#208)
- [ ] 5.5 Pruebas del store: lo que se manda, lo que se lee, y el estado tras un rechazo
- [ ] 5.6 Mutar el store y confirmar que las pruebas caen

## 6. Cierre

- [ ] 6.1 Suite completa de API y de navegador en verde, con los números medidos
- [ ] 6.2 `ruff`, `tsc --noEmit` y `next lint` limpios
- [ ] 6.3 Actualizar la entrada de estado de `CLAUDE.md` con lo medido, no con lo esperado
- [ ] 6.4 Archivar el cambio con `/opsx:archive` para que `openspec/specs/` refleje el sistema real
