# Tasks: la integración con el AI Service

Plan de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

## Fase 1 — Sincronización incremental

- [x] `updated_since` en `GET /catalog/norms` y `GET /documents/`
- [x] Convive con la paginación y los filtros que ya existen

## Fase 2 — Versiones y articulado histórico

- [x] `GET /catalog/norms/{norm_id}/versions`
- [x] `vigente_el` en el endpoint de artículos, con `valid_to IS NULL` bien tratado

## Fase 3 — Descarga verificable

- [x] `checksum_sha256` en la respuesta del enlace de descarga

## Fase 4 — El contrato

- [x] `X-Has-More` y `X-Page-Limit` derivadas para las rutas paginadas
- [x] `X-Tenant-Id` descrita como respaldo de desarrollo

## Fase 5 — Pruebas

- [x] El corte incremental, incluido el borde de `>` contra `>=`
- [x] El articulado de una fecha pasada, y de una fecha sin texto
- [x] Mutaciones: invertir la condición de vigencia, y quitar el checksum
