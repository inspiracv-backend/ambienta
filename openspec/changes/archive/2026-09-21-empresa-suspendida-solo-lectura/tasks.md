# Tasks: Una empresa suspendida queda en solo lectura

## Supuestos

**Vigentes (medidos el 21-sep):**
- `tenants.status` admite `trial`, `active`, `suspended`, `closed`.
- Solo `acceso_invitado` mira el estado hoy.
- `tenants` no lleva `tenant_id`: se lee con la sesión del tenant sin RLS.

**A confirmar:** las dos preguntas abiertas de `proposal.md`.

## Fase 0 — Prerrequisitos

- [x] Decisión tomada (plan de cierre, §6, decisión 2)

## Fase 1 — API

- [x] `ESTADOS_SOLO_LECTURA` en un solo lugar
- [x] Guarda en `exigir_permiso_de_la_ruta`, antes del corte sin Clerk, sobre la empresa efectiva y la de la sesión
- [x] 403 con `empresa_en_solo_lectura`
- [x] Pruebas: escribir en suspendida o cerrada da 403; leer sigue; una activa no se bloquea; el gestor en los dos sentidos; mutación de la guarda

## Fase 2 — Avisos

- [x] El cron salta las empresas en solo lectura
- [x] El informe cuenta las empresas en pausa
- [x] Prueba de que una suspendida no entra a la corrida

## Fase 3 — Web

- [x] Aviso en el tablero cuando la empresa está en solo lectura
- [x] El mensaje de la API llega tal cual a los errores de escritura

## Lo que aparecio al hacerlo

- **`crm`, `gestor` e `iso14001` se montaban sin `exigir_permiso_de_la_ruta`**
  desde la migracion a FastAPI: 30 escrituras sin permiso, que la suspension
  tampoco alcanzaba. Se vio en el navegador —una empresa suspendida creo un
  aspecto ISO con todas las pruebas en verde—. Ahora la llevan, y
  `test_guarda_en_todas_las_rutas.py` exige la guarda en toda ruta sin motivo
  declarado.
- **Un gestor no podia actuar por su cliente con Clerk**: la guarda buscaba a la
  persona con la sesion del cliente y RLS se la escondia. Ahora la persona y sus
  permisos se leen en su empresa (`test_gestor_con_clerk.py`).
- **Comentar es escribir**: `comentarios` no pasa por la guarda de permisos y
  ahora si por la de solo lectura (`exigir_escritura_en_empresa_activa`).
- `closed` se mostraba como activo en la web; ahora es `cerrado`.
