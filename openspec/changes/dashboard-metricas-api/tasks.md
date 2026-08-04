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

- [ ] Crear `apps/api/app/services/dashboard.py` con `get_dashboard_metrics()`
  - [ ] Query agregada para compliance % global (COUNT sobre `article_compliance`)
  - [ ] Query para contar NC abiertas (`nonconformity` donde `status != 'closed'`)
  - [ ] Reutilizar `get_upcoming_obligations()` para obligaciones por vencer
  - [ ] Reutilizar `get_overdue_obligations()` para obligaciones vencidas
  - [ ] Query para proximo vencimiento critico (ORDER BY `due_at` LIMIT 1)
  - [ ] Agrupar metricas por `facility_id` para la tabla multi-planta
- [ ] Crear `apps/api/app/routers/dashboard.py` con `GET /metrics`
- [ ] Registrar router en `apps/api/app/main.py`
- [ ] Verificar con curl que el endpoint responde correctamente con ambos tenants

## Fase 2 — Frontend: Mapeo de Facilities

- [ ] En `tenants-store.tsx`, cargar facilities por tenant despues de cargar tenants
- [ ] Mapear `facility` -> `Plant` en `mapApiTenant()`: `id`, `tenantId`, `nombre` (name), `comuna` (commune_code), `region` (region_code)
- [ ] Verificar que `DevRoleSwitcher` muestra los nombres de tenant correctos (ya no depende de mockTenants IDs)

## Fase 3 — Frontend: Dashboard conectado

- [ ] Crear tipo `DashboardMetrics` en `apps/web/lib/dashboard-metrics.ts` basado en el contrato del endpoint
- [ ] Refactorizar `dashboard/page.tsx`:
  - [ ] Reemplazar imports de mocks por llamada a `api.get('/dashboard/metrics')`
  - [ ] Agregar estados: `loading`, `error`, `metrics`
  - [ ] Skeleton loading en hero card y contadores
  - [ ] Error state con mensaje amigable y boton de reintentar
- [ ] Pasar `metrics.facilities` a `MultiPlantTable` en vez de `computePlantMetrics()`
- [ ] Pasar `metrics.critical_deadline` a `DashboardHeroCard` en vez de calculo local
- [ ] Pasar contadores de `metrics.global` a los 3 `MetricCounter`
- [ ] Mantener `computePlantMetrics()` como fallback si la API no responde

## Fase 4 — Verificacion

- [ ] Login como admin_empresa tenant 1: Dashboard muestra datos reales
- [ ] Login como admin_empresa tenant 2: Dashboard muestra datos distintos (aislamiento RLS)
- [ ] Tabla multi-planta muestra facilities como plantas
- [ ] Si se apaga la API, el Dashboard muestra error state (no crash)
- [ ] Tiempo de carga del endpoint <500ms con datos seed

---

## Orden sugerido

Fase 1 primero — sin el endpoint, no hay nada que conectar. Fase 2 puede ir
en paralelo (no depende del endpoint de dashboard). Fase 3 depende de ambas.
Fase 4 al final.

**Estimacion:** cambio mediano. Un servicio nuevo, un router nuevo, refactor
de un page y un ajuste al store. No hay cambios de schema ni migraciones.
