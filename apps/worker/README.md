# apps/worker

**Esta carpeta no tiene un servicio, y eso es una decision, no una tarea
pendiente.** El trabajo en segundo plano vive en `apps/api/app/tareas/` y se
dispara desde cron.

## Que habia aca

Un `package.json` con `@nestjs/common` y un `src/main.ts` con un
`console.log("Worker Ambienta - Placeholder")`. Sobraba de antes de que
**ADR-005 unificara `api`, `worker` y `ai-service` en Python**, y se borro el
27-ago-2026 al cerrar la epica #22.

No era inofensivo: `apps/*` esta en los workspaces de npm, asi que cada
`npm install` se bajaba NestJS y `ts-node` para sostener una linea que imprimia
un texto. Y hacia creer, a quien mirara el arbol del repositorio, que existia un
servicio que no existia.

## Donde esta el trabajo en segundo plano

| Que | Donde |
|---|---|
| Avisos de vencimiento: generar y despachar | `apps/api/app/tareas/avisos.py` |
| Rotacion del registro de actividades | `apps/api/app/tareas/rotar_auditoria.py` |
| Sincronizacion del catalogo con la BCN | `apps/api/app/tareas/sincronizar_bcn.py` |
| Todas, por linea de comandos | `python -m app.tareas <tarea>` |

```
0 7 * * *   docker compose exec -T api python -m app.tareas avisos
0 3 1 * *   docker compose exec -T api python -m app.tareas rotar-auditoria
```

## Por que no hay cola en Redis

La issue #118 pedia "Worker con BullMQ", que es una libreria de Node; ADR-005 ya
habia dicho que con el backend en Python **BullMQ deja de aplicar**, y proponia
ARQ o Celery sobre Redis.

Se implemento sin Redis, y conviene decir por que porque se aparta del ADR:
`notifications` **ya era una cola** —`status` con `queued` por defecto,
`scheduled_at`, `sent_at`, `provider_message_id`, `dedupe_key` con indice unico
y un indice parcial sobre los pendientes—. Lo unico que le faltaba era el estado
de reintento, que agrego `db/19`.

Y hay una razon de correccion, no solo de ahorro: **la fila del aviso y el hecho
que lo causa se escriben en la misma transaccion**. Si la evaluacion de la
obligacion se deshace, el aviso se deshace con ella. Con la cola en Redis son
dos almacenes que pueden discrepar, y las dos formas de discrepar son malas: un
correo enviado por una obligacion que se revirtio, o una fila `queued` que
ningun trabajo va a atender porque el encolado fallo despues del commit.

Lo que se cede es rendimiento. Postgres mueve ordenes de magnitud menos trabajos
por segundo que Redis; para decenas de avisos al dia por empresa, sobra. El
contrato —`despacho.Transporte` y los estados de `notifications`— sobrevive si
algun dia hay que cambiarlo.

## Cuando SI hara falta un proceso propio

Hoy el cron alcanza porque las tareas son diarias y cortas. Un proceso residente
se justifica cuando aparezca **trabajo disparado por el usuario que no puede
esperar al proximo cron**: generar un informe pesado, procesar un archivo
grande, o el `ai-service`. Ese dia esta carpeta vuelve, en Python.
