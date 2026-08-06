# Progreso: Sistema de Actores, Roles, Multi-tenancy y Audit Log

**Ultima actualizacion:** 2026-08-04

## Estado actual

**Fase actual:** Spec completada, pendiente de aprobacion.
**Nada implementado del checklist** — la spec fue escrita pero nunca aprobada formalmente.

> **Nota:** Gran parte de lo que esta spec propone fue implementado por otra via
> (schema PostgreSQL con RLS, migracion a FastAPI, seed de datos). Sin embargo,
> esa implementacion no siguio el flujo SDD: se codifico sin aprobar esta spec
> primero. Los puntos del checklist que coinciden con lo implementado deben
> reconciliarse, no marcarse como "hechos".

## Completado

- [x] Spec escrita: proposal.md + design.md + tasks.md (commit ce017fd)
- [x] Fuentes adjuntas: analisis de actores v1 + prompt de implementacion

## Lo que existe en el codigo vs lo que pide la spec

| Punto de la spec | Estado en el codigo | Reconciliado? |
|---|---|---|
| Tabla `users` con roles | Existe en `db/01_schema.sql` | No — la spec pide Drizzle ORM, se implemento con SQLAlchemy |
| RLS por tenant | 37 politicas implementadas | No — la spec pide `packages/db`, se implemento en FastAPI + raw SQL |
| Audit log inmutable | Tabla existe con REVOKE UPDATE/DELETE | Parcial — falta verificar que el contrato coincide |
| Auth con JWT propio | **Reemplazado por Clerk** (ADR-006) | La spec de auth de actores queda obsoleta — va por `integracion-clerk-auth` |
| RBAC con 39 permisos | Modelado en BD, no implementado en API | No |
| Sub-tenancy (Gestor) | Schema existe, logica no implementada | No |
| Cliente Invitado | Schema existe, flujo no implementado | No |

## Siguiente paso

1. Decidir si esta spec se **cierra como reemplazada** (el schema ya existe por otra via + auth va por Clerk) o si se **actualiza** para reflejar el stack real (FastAPI + SQLAlchemy en vez de Drizzle + NestJS)
2. Si se actualiza: quitar toda la seccion de Auth (va en `integracion-clerk-auth`) y reconciliar el checklist con lo implementado

## Blockers

- La seccion de Auth de esta spec esta obsoleta — ADR-006 eligio Clerk
- La spec asume Drizzle ORM y NestJS; el stack real es SQLAlchemy + FastAPI
- Sin decision del equipo sobre que hacer con esta spec, no se puede avanzar
