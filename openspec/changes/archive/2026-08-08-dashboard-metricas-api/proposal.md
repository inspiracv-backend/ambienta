# Proposal: Dashboard conectado a API de Metricas

Fuentes: `openspec/analisis/seccion-c-dashboard.md` (RF-47, RF-48, RF-49, RF-51) · `apps/web/app/(dashboard)/dashboard/page.tsx` (estado actual) · `apps/api/app/services/obligations.py` y `apps/api/app/services/compliance.py` (servicios existentes).

## Contexto

El Dashboard (S-06/S-07) hoy renderiza datos correctamente pero los obtiene
de archivos mock importados directamente (`mockTenants`, `mockObligations`,
`mockNonConformities`). Esto ocurre a pesar de que:

1. Los **stores** de React (`tenants-store`, `obligations-store`, `audits-store`)
   ya se conectan a la API real y cargan datos del backend.
2. El **backend** ya tiene servicios de logica de negocio que calculan metricas:
   - `get_compliance_stats(db, matrix_id)` — % de cumplimiento por matriz
   - `get_upcoming_obligations(db, tenant_id, days)` — obligaciones por vencer
   - `get_overdue_obligations(db, tenant_id)` — obligaciones vencidas
   - `get_audit_summary(db, audit_id)` — resumen de auditoria
3. El **RLS** ya esta activo con `SET LOCAL ROLE ambienta_app`, por lo que las
   queries son seguras por tenant.

### Que se rompe hoy

- El Dashboard muestra **ceros o datos inventados** que no reflejan el estado
  real de la base de datos.
- Las instalaciones (`plants`) del Dashboard vienen de `mockTenants` y no de
  la API de `facilities`, por lo que la tabla multi-planta (S-07) esta vacia
  o muestra plantas inexistentes.
- Si un usuario crea una obligacion o registra cumplimiento via la API, el
  Dashboard no se entera.
- El contador "No Conformidades abiertas" usa `mockNonConformities` aunque el
  store de auditorias ya tiene datos reales.

## Objetivo

Conectar el Dashboard a datos reales en dos capas:

1. **Backend**: un endpoint `GET /dashboard/metrics` que agregue en una sola
   llamada las metricas que hoy el frontend calcula localmente sobre mocks.
2. **Frontend**: reemplazar las importaciones de mocks por llamadas al nuevo
   endpoint y/o a los stores existentes.

## Alcance

### Incluye

- Endpoint `GET /dashboard/metrics` que devuelva:
  - % de cumplimiento global (derivado de `compliance_stats`)
  - Contadores: articulos en incumplimiento, NC abiertas, obligaciones por vencer
  - Proximo vencimiento critico (nombre, dias restantes, semaforo)
  - Metricas por planta para la tabla S-07
- Servicio `dashboard.py` en el backend que orqueste los servicios existentes
- Mapeo de `facilities` como `plants` en `tenants-store`
- Refactorizar `dashboard/page.tsx` para consumir la API en vez de mocks
- Skeleton/loading state mientras se cargan metricas
- Error state si la API no responde (fallback a ultimo dato conocido)

### NO incluye

- Configuracion del calculo del % de cumplimiento (RF-51, pertenece a Seccion D)
- Cache/invalidacion avanzada de metricas (optimizacion futura)
- Vista Superadmin cross-tenant (requiere endpoint sin tenant_id, fuera de scope)
- Websockets o polling para actualizacion en tiempo real

## Criterios de aceptacion

- [ ] Al hacer login como admin_empresa del tenant 1, el Dashboard muestra metricas reales del tenant 1 (no ceros ni datos mock)
- [ ] Al hacer login como admin_empresa del tenant 2, muestra metricas del tenant 2 (aislamiento RLS)
- [ ] La tabla multi-planta (S-07) muestra las facilities del tenant como plantas con metricas por planta
- [ ] Los 3 contadores (incumplimiento, NC abiertas, por vencer) reflejan datos de la BD
- [ ] El hero card muestra el proximo vencimiento critico real
- [ ] Si la API no responde, se muestra un estado de error, no un crash
- [ ] El tiempo de carga del Dashboard con datos reales es <2 segundos

## Alternativas consideradas

**Consumir los stores directamente sin endpoint nuevo.** El Dashboard necesita
datos agregados (conteos, porcentajes) que hoy no estan en los stores. Calcular
todo en el frontend requeriria cargar TODAS las obligaciones y NC del tenant
solo para contar — ineficiente con volumenes reales. Un endpoint de metricas
hace la agregacion en la BD.

**Multiples llamadas a endpoints existentes.** Se podria llamar a
`/obligations/upcoming`, `/obligations/overdue`, `/compliance/matrices/{id}/stats`
y `/audits/nonconformities/` por separado. Pero eso son 4+ requests con
waterfalls, y el frontend debe saber que endpoints combinar. Un endpoint
agregado es mas limpio y mas rapido.
