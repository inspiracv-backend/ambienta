# Progreso: Dashboard conectado a API de Metricas

**Ultima actualizacion:** 2026-08-05

## Estado actual

**Fases 1 y 3 completadas.** Rama `feat/dashboard-metricas-api`, que sale de
`002-backend-api-stores-integracion` directo — no se apila sobre la cadena de
Clerk.

Fase 2 se saca de la entrega a proposito (ver abajo). Fase 4 esta verificada
salvo lo que exige una base levantada.

## Completado

- [x] Spec: proposal.md + design.md + tasks.md (commit ac17576)
- [x] **Backend**
  - [x] `services/dashboard.py` — 6 consultas fijas, sin N+1 por planta
  - [x] `routers/dashboard.py` — `GET /api/v1/dashboard/metrics`
  - [x] `schemas/dashboard.py` — contrato Pydantic (de aca sale el OpenAPI)
  - [x] 22 tests, sin base de datos levantada
- [x] **Frontend**
  - [x] `lib/dashboard-metrics.ts` — tipos de la API + adaptador
  - [x] `dashboard/page.tsx` — skeleton, banner de error y respaldo a mocks
  - [x] 15 tests nuevos del adaptador (190 en total en el repo)

## Verificacion hecha

| Que | Resultado |
|---|---|
| `pytest` (API) | 22 passed |
| `vitest` (web) | 190 passed en 14 archivos |
| `tsc --noEmit` | 0 |
| `next lint` | 0 |
| `next build` | 0 |
| `ruff check` sobre lo nuevo | All checks passed |

**Lo que NO esta verificado:** el endpoint nunca corrio contra Postgres. Docker
Desktop no esta arriba en la maquina de desarrollo. Las consultas se validan
compilandolas contra el dialecto de Postgres (`test_todas_las_consultas_compilan`),
que atrapa columnas inexistentes pero no errores de datos ni de RLS.

## Bugs preexistentes encontrados y corregidos

`services/compliance.py` estaba roto contra el modelo real. No fallaba porque
nadie llamaba a esos endpoints:

| Usaba | La columna real es |
|---|---|
| `ArticleCompliance.compliance_answer` | `compliance_status` |
| `art.evaluated_by` / `evaluated_at` | `assessed_by` / `assessed_at` |
| Validaba contra `not_evaluated` | El CHECK admite `partial` y `pending`, no `not_evaluated` |

`get_compliance_stats` lanzaba `AttributeError` y `evaluate_article` habria sido
rechazado por la base. El test `test_todas_las_consultas_compilan` existe para
que esto no vuelva a pasar en silencio.

## Decisiones tomadas durante la implementacion

| Decision | Por que | Estaba en la spec? |
|---|---|---|
| COUNT agregado en vez de reusar `get_upcoming_obligations()` | Ese servicio devuelve entidades; contar en Python lo que Postgres cuenta solo es lo que el §7 del design pide evitar | Contradice §1, sigue §7 |
| Pendiente = `NOT IN ('accepted','closed')` | El servicio viejo usaba `IN ('open','draft')` y perdia `in_progress` y `submitted` | No |
| `days_remaining` con `ceil`, no `.days` | Para coincidir con el `Math.ceil` que la tarjeta hero ya usaba. Truncando, 20 horas se leia "0 dias" en la API y "1 dia" en pantalla | No |
| `partial` cuenta en el denominador pero no en el numerador | Dos cumplimientos parciales no equivalen a uno completo | No |
| `commune_code` / `region_code` en la respuesta | `ReporteCumplimientoPdf` los usa; sin ellos habria que pedir `/facilities` aparte | No |
| Fase 2 fuera de la entrega | Mapear facilities en el store deja `DeadlinesList` vacia: los mocks de obligaciones referencian IDs de mock | No |

## Siguiente paso

1. **Levantar Docker Desktop** y correr la verificacion de Fase 4:
   - `GET /dashboard/metrics` con el tenant 1 y con el tenant 2
   - Confirmar que devuelven datos distintos (aislamiento RLS)
   - Medir el tiempo de respuesta
2. Cargar `db/02_seed.sql`, que **no** esta en el init de docker-compose (solo
   van `01_schema.sql` y `03_seed_catalogos.sql`). Sin el no hay tenants ni
   obligaciones y todas las metricas dan 0 — que seria un cero correcto, pero
   no prueba nada.

## Blockers

- Docker Desktop apagado: sin eso no hay verificacion contra base real.
- El seed de demo no se carga solo con `docker compose up`.
