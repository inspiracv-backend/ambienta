# Design: Dashboard conectado a API de Metricas

Documento tecnico de [`proposal.md`](./proposal.md).

---

## 1. Endpoint `GET /dashboard/metrics`

### Request

```
GET /api/v1/dashboard/metrics
Headers:
  X-Tenant-Id: <uuid>
Query params:
  facility_id?: <uuid>  (opcional, filtra por planta)
  days_ahead?: int       (default 30, para "por vencer")
```

### Response (200 OK)

```json
{
  "tenant_id": "uuid",
  "generated_at": "2026-08-04T12:00:00Z",
  "global": {
    "compliance_percentage": 75.3,
    "articles_evaluated": 40,
    "articles_non_compliant": 5,
    "total_obligations": 42,
    "nc_open": 3,
    "obligations_upcoming": 8,
    "obligations_overdue": 2
  },
  "critical_deadline": {
    "obligation_id": "uuid",
    "title": "Declaracion RETC anual",
    "code": "OBL-001",
    "due_at": "2026-08-15T00:00:00Z",
    "days_remaining": 11,
    "status": "open"
  } | null,
  "facilities": [
    {
      "facility_id": "uuid",
      "name": "Planta Santiago",
      "compliance_percentage": 80.0,
      "non_compliant_count": 2,
      "nc_open_count": 1,
      "critical_deadline": {
        "title": "...",
        "due_at": "...",
        "days_remaining": 5
      } | null
    }
  ]
}
```

### Logica de agregacion

El servicio `get_dashboard_metrics()` resuelve todo en **6 consultas fijas**,
independientes de cuantas plantas tenga el tenant.

1. **Contadores de obligaciones** (1 consulta): total pendientes, por vencer y
   vencidas, con tres `COUNT(...) FILTER (WHERE ...)` sobre el mismo `FROM`.
2. **NC abiertas** (1): `GROUP BY facility_id`.
3. **Compliance %** (1): join `article_compliance → matrix_norm → matrix`.
4. **Proximo critico** (1): `DISTINCT ON (facility_id) ORDER BY due_at`, que en
   Postgres da el "top 1 por grupo" sin subconsulta ni window function.
5. **Compliance por planta** (1): lo mismo que 3 pero con `GROUP BY`.
6. **Plantas** (1): se parte de `facilities` y no de las obligaciones, para que
   una planta sin nada cargado aparezca igual en 0.

Todo filtrado por RLS via `SET LOCAL ROLE ambienta_app`, y ademas por
`tenant_id` explicito (CLAUDE.md §4: RLS es la segunda barrera, no la unica).

### Correcciones al leer el modelo real (05-ago-2026, durante la implementacion)

La v1 de este diseño se escribio sobre supuestos que el esquema no cumple:

| La spec decia | La realidad | Consecuencia |
|---|---|---|
| `ArticleCompliance.compliance_answer` | La columna es **`compliance_status`** | `compliance_answer` **no existe**. `services/compliance.py` la usaba: `get_compliance_stats` lanzaba `AttributeError` en runtime. Corregido de paso |
| Valores `not_evaluated` | El CHECK admite `compliant`, `non_compliant`, **`partial`**, `not_applicable`, **`pending`** | `evaluate_article` validaba contra una lista que la base rechaza, y omitia dos valores validos. Corregido |
| `evaluated_by` / `evaluated_at` | Son **`assessed_by`** / **`assessed_at`** | Mismo error, mismo archivo. Corregido |
| Reusar `get_upcoming_obligations()` | Devuelve entidades completas | Traer 500 obligaciones para hacer `len()` es justo lo que el §7 de este diseño pide evitar. Se escriben COUNT agregados |
| Pendiente = `status IN ('open','draft')` | El CHECK admite 8 estados | Dejaba fuera `in_progress` y `submitted`: una obligacion en la que alguien ya empezo a trabajar desaparecia del tablero. Se cuenta **por exclusion** (`NOT IN ('accepted','closed')`) para que agregar un estado nuevo no reabra el hueco |

**Sobre el porcentaje.** `not_applicable` sale del denominador; `pending` se
queda dentro (si no, una matriz con un articulo evaluado mostraria 100%);
`partial` cuenta en el denominador pero no en el numerador, porque dos
cumplimientos parciales no equivalen a uno completo.

**Sobre `days_remaining`.** Se redondea hacia arriba (`ceil`), no con
`timedelta.days` que trunca, para coincidir con el `Math.ceil` que la tarjeta
hero ya usaba. Con truncamiento, algo que vence en 20 horas se leeria "0 dias"
en la API y "1 dia" en pantalla.

---

## 2. Servicio backend `dashboard.py`

```
apps/api/app/services/dashboard.py
```

Funciones:

- `get_dashboard_metrics(db, tenant_id, facility_id?, days_ahead?) -> dict`
- Reutiliza los servicios existentes donde sea posible
- Para metricas por facility, ejecuta queries agrupadas con `GROUP BY facility_id`
  en vez de N+1 queries

---

## 3. Router backend

```
apps/api/app/routers/dashboard.py
```

Un solo endpoint:

```python
@router.get("/metrics")
def dashboard_metrics(
    facility_id: UUID | None = None,
    days_ahead: int = 30,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    return get_dashboard_metrics(db, tenant_id, facility_id, days_ahead)
```

Se registra en `main.py` como `api_router.include_router(dashboard.router)`.

---

## 4. Mapeo facilities -> plants en tenants-store

`mapApiTenant()` actualmente devuelve `plants: []`. Cambio:

```typescript
// Despues de cargar tenants, cargar facilities por tenant
const facilities = await api.get<Record<string, unknown>[]>(
  '/facilities/', { tenantId: tenant.id }
);

return {
  ...tenantData,
  plants: facilities.map(f => ({
    id: String(f.id),
    tenantId: String(tenant.id),
    nombre: String(f.name),
    comuna: String(f.commune_code ?? ''),
    region: String(f.region_code ?? ''),
  })),
};
```

---

## 5. Refactor del Dashboard page

### Antes (mocks directos)

```tsx
import { mockTenants } from '@/mocks/tenants';
import { mockObligations } from '@/mocks/obligations';
import { mockNonConformities } from '@/mocks/audits';
// ... calculo local de metricas
```

### Despues (API)

```tsx
const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(false);

useEffect(() => {
  if (!user?.tenantId) return;
  api.get<DashboardMetrics>('/dashboard/metrics', { tenantId: user.tenantId })
    .then(setMetrics)
    .catch(() => setError(true))
    .finally(() => setLoading(false));
}, [user?.tenantId]);
```

El tipo `DashboardMetrics` se define en el frontend basado en el contrato
del endpoint (seccion 1).

---

## 6. Consideraciones de seguridad

- El endpoint usa `get_tenant_db` que aplica `SET LOCAL ROLE ambienta_app` +
  `set_config('ambienta.tenant_id', ...)`. RLS garantiza aislamiento.
- No se expone informacion cross-tenant. La vista Superadmin se implementara
  en una propuesta separada con un endpoint distinto.
- El `facility_id` del query param se valida automaticamente por RLS: si no
  pertenece al tenant, las queries devuelven 0 resultados.

## 7. Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| No hay datos seed para metricas reales | Verificar que el seed SQL incluya obligaciones y article_compliance con datos variados |
| El endpoint es lento con muchas obligaciones | Usar queries agregadas (COUNT, GROUP BY) en vez de cargar entidades completas |
| La tabla multi-planta esta vacia si no hay facilities en el tenant | Mostrar empty state con mensaje "No hay plantas configuradas" |
