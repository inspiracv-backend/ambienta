# Tasks: El registro de actividades, visible y completo

## Supuestos

**Vigentes (medidos el 21-sep):** `audit_log` admite `download`; el rol de la
aplicación solo inserta y lee; `GET /system/audit-log` ya exige permiso y
ordena del más reciente.

**A confirmar:** las preguntas abiertas de `proposal.md`.

## Fase 0 — Prerrequisitos

- [x] Guarda y orden de `GET /system/audit-log` (21-sep, antes de este cambio)

## Fase 1 — API

- [x] `POST /emisiones` con `report.generate`, lista cerrada de documentos y `validar_visible`
- [x] Una empresa suspendida puede anotar su emisión
- [x] `desde` y `hasta` en días de la empresa, y `actor_nombre`
- [x] Pruebas, incluida la mutación de cada guarda

## Fase 2 — Web

- [x] Tipos de entidad que faltaban y `otro` en `packages/shared`
- [x] Traducción de fila de la API a `AuditLogEntry`, con pruebas
- [x] `audit-log-store` lee la API; aviso si la página vino cortada
- [x] Filtro de fechas contra el servidor
- [x] El informe de auditoría, la matriz de aspectos y los reportes anotan su emisión
