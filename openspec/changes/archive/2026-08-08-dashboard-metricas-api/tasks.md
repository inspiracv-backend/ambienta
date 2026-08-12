# Tasks: Dashboard conectado a API de Metricas

Plan de implementacion de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

> **Nada de esto se ejecuta hasta que la propuesta este aprobada**
> (CLAUDE.md §1: solo se implementan features con spec aprobada).

---

## Supuestos

| # | Supuesto | Por que se tomo | Si se rechaza |
|---|---|---|---|
| S-1 | Un solo endpoint `/dashboard/metrics` en vez de multiples llamadas | Reduce waterfalls y simplifica el frontend | Se usan los endpoints existentes por separado |
| S-2 | El % de cumplimiento se calcula sobre `ArticleCompliance` | Es la entidad que modela la evaluacion articulo por articulo | Si se usa otro criterio, cambia la query |
| S-3 | Las facilities se mapean como plants 1:1 | La BD tiene `facilities` y el frontend espera `plants` | Si hay otra relacion, se ajusta el mapeo |
| S-4 | El seed SQL tiene datos suficientes para metricas no-cero | Sin datos, el Dashboard mostrara ceros reales (que no es bug) | Se agrega seed data |

---

## Fase 1 — Backend: Servicio y Endpoint

> **Completada 05-ago-2026.** Rama `feat/dashboard-metricas-api`. 22 tests.

- [x] Crear `apps/api/app/services/dashboard.py` con `get_dashboard_metrics()`
  - [x] Query agregada para compliance % global (COUNT sobre `article_compliance`)
  - [x] Query para contar NC abiertas
  - [x] ~~Reutilizar `get_upcoming_obligations()`~~ → **COUNT agregado**. Ese
        servicio devuelve entidades completas: traer 500 obligaciones para
        hacer `len()` es lo que el §7 del design pide evitar
  - [x] ~~Reutilizar `get_overdue_obligations()`~~ → idem, mismo COUNT
  - [x] Query para proximo vencimiento critico (`DISTINCT ON` por planta)
  - [x] Agrupar metricas por `facility_id` para la tabla multi-planta
- [x] Crear `apps/api/app/routers/dashboard.py` con `GET /metrics`
- [x] Contrato Pydantic en `apps/api/app/schemas/dashboard.py` (no estaba en la
      spec, pero sin el no hay OpenAPI del que derivar los tipos — CLAUDE.md §3)
- [x] Registrar router en `apps/api/app/main.py` (94 rutas)
- [ ] Verificar con curl que el endpoint responde con ambos tenants — **bloqueado:
      Docker Desktop no esta corriendo en la maquina de desarrollo**

## Fase 2 — Frontend: Mapeo de Facilities

> **Se saca de esta entrega a proposito.** El endpoint de metricas ya devuelve
> las facilities con sus metricas, asi que la tabla S-07 (que era el motivo del
> mapeo, segun proposal.md) ya funciona sin tocar el store.
>
> Hacerlo aca ademas **rompe la lista de proximos vencimientos**: si
> `tenant.plants` pasa a traer IDs reales, `mockObligations` —que referencia IDs
> de mock— deja de cruzar y `DeadlinesList` queda vacia. Los dos cambios tienen
> que moverse juntos, y eso es ABA-67 (Conectar Obligaciones a API real).

- [ ] `tenants-store.tsx`: cargar facilities por tenant → **movido a ABA-67**
- [ ] Mapear `facility` → `Plant` en `mapApiTenant()` → **movido a ABA-67**

## Fase 3 — Frontend: Dashboard conectado

> **Completada 05-ago-2026.** 15 tests en `lib/dashboard-metrics.test.ts`.

- [x] Tipos `ApiDashboardMetrics` + adaptador `fromApiMetrics()`
- [x] Refactorizar `dashboard/page.tsx`:
  - [x] Llamada a `api.get('/dashboard/metrics')` con `AbortController`
  - [x] Estados: `cargando`, `sinConexion`, `metrics`
  - [x] Skeleton que conserva la altura, para que no salte el layout
  - [x] Banner de error con boton de reintentar
- [x] Pasar las metricas de la API a `MultiPlantTable`
- [x] Pasar `critical_deadline` a `DashboardHeroCard`
- [x] Pasar contadores de `global` a los 3 `MetricCounter`
- [x] Mantener `computePlantMetrics()` como respaldo si la API no responde

### Agregado durante la implementacion (no estaba en la spec)

- [x] **`commune_code` y `region_code` en la respuesta por planta.**
      `ReporteCumplimientoPdf` los imprime en la cabecera de cada planta; sin
      ellos habria que pedir `/facilities` aparte solo para eso
- [x] **`obligation_id` en el vencimiento critico**, para poder enlazar al
      detalle de la obligacion (RF-49)
- [x] Contratos de `DashboardHeroCard` y `PlantMetric` acotados a lo que los
      componentes usan: la API devuelve agregados, no entidades, y exigir un
      `Obligation` completo obligaba a inventar campos
- [x] Corregidos tres bugs preexistentes en `services/compliance.py` (ver design §Correcciones)

## Fase 4 — Verificacion

- [x] `pytest`: 22 tests del backend
- [x] `vitest`: 190 tests del frontend (15 nuevos del dashboard)
- [x] `tsc --noEmit`, `next lint`, `next build`: los tres en 0
- [x] `ruff check`: limpio en los archivos nuevos
- [ ] Login como admin_empresa tenant 1: datos reales — **bloqueado por Docker**
- [ ] Login como admin_empresa tenant 2: datos distintos (RLS) — **bloqueado por Docker**
- [ ] Tiempo de carga del endpoint <500ms — **bloqueado por Docker**
- [x] Si la API no responde, el Dashboard no crashea: cae al respaldo y avisa
      que los numeros son de ejemplo

---

## Orden sugerido

Fase 1 primero — sin el endpoint, no hay nada que conectar. Fase 2 puede ir
en paralelo (no depende del endpoint de dashboard). Fase 3 depende de ambas.
Fase 4 al final.

**Estimacion:** cambio mediano. Un servicio nuevo, un router nuevo, refactor
de un page y un ajuste al store. No hay cambios de schema ni migraciones.
