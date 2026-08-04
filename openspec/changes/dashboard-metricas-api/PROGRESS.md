# Progreso: Dashboard conectado a API de Metricas

**Ultima actualizacion:** 2026-08-04

## Estado actual

**Fase actual:** Spec completada, pendiente de aprobacion.
**Nada implementado** — siguiendo SDD, se espera aprobacion antes de escribir codigo.

## Completado

- [x] Spec: proposal.md + design.md + tasks.md (commit ac17576)

## Siguiente paso

1. Aprobar la spec
2. Fase 1: crear servicio y endpoint `GET /dashboard/metrics` en FastAPI
3. Fase 2: mapeo de facilities en el store (puede ir en paralelo con Fase 1)

## Dependencias

- **Clerk auth** (spec `integracion-clerk-auth`): si se implementa Clerk primero, el endpoint de dashboard necesitara JWT en vez del header X-Tenant-Id. No es blocker — el endpoint usa `get_tenant_db()` que abstraera la fuente del tenant_id
- Los datos de seed deben tener metricas no-cero para verificar (supuesto S-4)

## Blockers

- Ninguno tecnico. Solo falta aprobacion de la spec.
