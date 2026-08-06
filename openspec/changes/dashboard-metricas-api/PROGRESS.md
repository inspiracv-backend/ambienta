# Progreso: Dashboard conectado a API de Metricas

**Ultima actualizacion:** 2026-08-05

## Estado actual

**Fases 1 y 3 completadas.** Rama `feat/dashboard-metricas-api`, que sale de
`002-backend-api-stores-integracion` directo — no se apila sobre la cadena de
Clerk.

Fase 2 se saca de la entrega a proposito (ver abajo). Fase 4 esta verificada
completa, incluida la prueba contra Postgres y el navegador.

## Completado

- [x] Spec: proposal.md + design.md + tasks.md (commit ac17576)
- [x] **Backend**
  - [x] `services/dashboard.py` — 6 consultas fijas, sin N+1 por planta
  - [x] `routers/dashboard.py` — `GET /api/v1/dashboard/metrics`
  - [x] `schemas/dashboard.py` — contrato Pydantic (de aca sale el OpenAPI)
  - [x] 24 tests, sin base de datos levantada
- [x] **Frontend**
  - [x] `lib/dashboard-metrics.ts` — tipos de la API + adaptador
  - [x] `dashboard/page.tsx` — skeleton, banner de error y respaldo a mocks
  - [x] Lista de proximos vencimientos conectada: sin eso el hero decia "SIDREP
        vencida" y la lista de abajo "no hay vencimientos proximos"
  - [x] 15 tests nuevos del adaptador (190 en total en el repo)

## Verificacion hecha

| Que | Resultado |
|---|---|
| `pytest` (API) | 24 passed |
| `vitest` (web) | 190 passed en 14 archivos |
| `tsc --noEmit` | 0 |
| `next lint` | 0 |
| `next build` | 0 |
| `ruff check` sobre lo nuevo | All checks passed |

### Verificacion end-to-end contra Postgres (05-ago-2026)

| Que | Resultado |
|---|---|
| `GET /dashboard/metrics` tenant 1 (Minera Andes) | 200 en **0,25 s** — 5 obligaciones, 1 NC, 4 plantas |
| `GET /dashboard/metrics` tenant 2 (EcoGestion) | 200 en **0,02 s** — 0 obligaciones, 0 NC, 1 planta |
| **Aislamiento RLS** | Datos distintos por tenant, sin filtraciones |
| Calculo del porcentaje | **40,0 %** exacto: 2 cumplen de 5 evaluados, el `not_applicable` fuera del denominador y el `pending` dentro |
| Dashboard en el navegador | Muestra los datos reales: 40 %, la SIDREP vencida y las 4 plantas con sus contadores |
| Enlace del vencimiento | Apunta a `/obligaciones/a0000021-…`, el id real (RF-49) |
| Estado de error | Con la API caida aparece el banner "no reflejan tu empresa" y no hay crash |
| Boton Reintentar | Recupera los datos reales al volver la API |

**Limitacion encontrada al probarlo:** con la API completamente caida no se
llega al Dashboard, porque la sesion tambien depende de la API y la pantalla
queda en "Cargando sesion". El banner cubre el caso de que falle el endpoint de
metricas mientras la sesion vive, no una caida total. Eso es del store de
sesion, no de esta pantalla.

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

La spec queda cerrada salvo la Fase 2, que se movio a ABA-67. Lo que sigue del
Dashboard depende de otros modulos:

- El nombre de la empresa en la cabecera sale de `mockTenants`, que no cruza con
  los ids reales del seed, asi que aparece vacio. Se arregla al conectar
  `tenants-store` (ABA-78).
- El respaldo sin conexion muestra ceros por lo mismo: los mocks de obligaciones
  referencian ids de mock.

## Notas para quien lo pruebe

`db/02_seed.sql` **no** esta en el init de `docker-compose.yml` (solo van
`01_schema.sql` y `03_seed_catalogos.sql`). Hay que cargarlo a mano:

```bash
docker compose exec -T postgres psql -U ambienta -d ambienta < db/02_seed.sql
```

Sin el no hay tenants ni obligaciones y todas las metricas dan 0 — un cero
correcto, pero que no prueba nada. Este PR le agrega al seed las filas de
`article_compliance` que faltaban, que eran el riesgo #1 del design.
