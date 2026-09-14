# Tasks: la normativa propia del tenant (bloque D, RF-10 y RF-11)

Plan de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

## Fase 1 — La base

- [x] `db/29_normativa_propia.sql`: `tenant_id` nulable en las tres tablas del catálogo
- [x] RLS con la política de dos lados, **sin `FORCE`**, y sus GRANT
- [x] Registrar el archivo en los **cinco** lugares

## Fase 2 — El servicio y la API

- [x] `services/normativa_propia.py`: registrar una norma propia con su versión y sus artículos
- [x] Endpoints bajo `/compliance` o `/catalog`, con el permiso de la matriz legal
- [x] Rechazar el intento de crear una norma sin dueño

## Fase 3 — Las pruebas que importan

- [x] La empresa B no ve la RCA de la A, ni sus artículos
- [x] El catálogo público se sigue viendo igual
- [x] **La sincronización de la BCN sigue funcionando** tras activar RLS
- [x] Mutaciones: quitar el `WITH CHECK`, y agregar `FORCE`

## Fase 4 — La interfaz

- [x] Cargar una norma propia desde la matriz legal
- [x] Distinguir visualmente pública / propia
