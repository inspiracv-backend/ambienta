# ADR-005: Stack de ejecución y topología de despliegue de Ambienta

**Estado:** `Propuesto` — pendiente de aprobación. **Reemplaza a ADR-002** (que sigue en `Propuesto` y ya es contradicho por el código).
**Fecha:** 2026-07-31
**Decisores:** equipo Ambienta — pendiente firma. Autor de la propuesta de stack e infraestructura: mentor senior. Objeción de escalabilidad levantada por: encargado.
**Categoría:** Arquitectura de software · Infraestructura
**Specs relacionadas:** `ADD-ambienta-backend-separado.md` · `openspec/changes/sistema-actores-roles-rbac/` · `docs/arquitectura/backend-arquitectura.md`

---

## Contexto

Convergen cuatro cosas que obligan a cerrar una decisión que lleva meses abierta:

1. **ADR-002 está sin aprobar y el código lo contradice.** Propone Fastify + tRPC + Drizzle + Neon + Hetzner. El repo real tiene NestJS 10 + Express, npm workspaces, ningún ORM y docker-compose sobre una VM con Caddy. `backend-arquitectura.md` §2 lo lista como deuda arquitectónica explícita.

2. **Propuesta de stack del mentor senior:** mover la API de negocio de Node.js a **FastAPI (Python)**. Esto invierte el principio 3 del ADD §2.2 ("IA en Python, API en Node.js").

3. **Propuesta de infraestructura del mentor senior** (diagrama "Sugerencia de Sistema"): servicios gestionados — Cloudflare Pages (frontend), Railway (API), Aiven (PostgreSQL + pgvector), Backblaze B2 (archivos), Resend (correo), Auth0/Keycloak (identidad), con subida directa por URL firmada.

4. **Objeción del encargado:** duda de que el stack escale a largo plazo y soporte muchos usuarios.

### Sobre la objeción de escalabilidad

Se documenta acá porque es la razón por la que existe este ADR, y porque **no se sostiene como criterio de decisión**:

- FastAPI corre sobre ASGI/uvicorn — mismo modelo asíncrono no bloqueante que Node. No es Django ni Flask sincrónico.
- Todo request de Ambienta hace un round trip a PostgreSQL con RLS activo. El framework deja de ser el cuello de botella mucho antes de que la carga sea relevante.
- El modelo de negocio es contrato anual con `limiteUsuarios` por tenant (`packages/shared/src/schemas/tenant.ts`), descrito por el equipo como *"no son usuarios transaccionales, como un SAP"*. La concurrencia real son cientos de sesiones en peaks predecibles (plazos RETC/SIDREP), no decenas de miles.
- Los cuellos de botella reales serán: PostgreSQL con RLS y JSONB pesado, throughput de subida de evidencia, latencia del servicio IA (el ADD estima 3-6 s/respuesta) y los jobs de sincronización BCN. **Ninguno depende de Node vs Python.**

**Hallazgo relevante:** no existe en todo el repositorio ningún RNF con meta de usuarios concurrentes, latencia o disponibilidad. Hay RNF-07 (aislamiento), RNF-08 (audit log), RNF-19 (backups), pero nada de capacidad. La objeción apunta a un requisito que nadie escribió. Este ADR propone uno (ver D6).

---

## Decisión

### D1 — Lenguaje de la API de negocio: **Python / FastAPI**

`apps/api`, `apps/worker` y `apps/ai-service` se unifican en Python. Se acepta la propuesta del mentor.

**Por qué:** el equipo es de 2 personas (ADR-002) y Python **ya es obligatorio** para `ai-service` (LangGraph, pgvector, procesamiento de XML de BCN y PDFs). Mantener dos lenguajes duplica toolchain, CI, convenciones y contexto mental para el mismo par de personas. Además el dominio favorece Python: parsing de XML BCN, OCR y RAG.

**Momento:** el NestJS actual son ~4 archivos sin lógica de negocio (`backend-arquitectura.md` §1: sin módulos, sin ORM, sin esquema, sin auth). Este es el punto más barato que va a existir para cambiar. En seis meses no lo será.

**Costo que se acepta explícitamente:** se pierde el compartir tipos vía Zod entre `apps/web` y la API. Los 18 schemas de `packages/shared` siguen sirviendo al frontend, pero el contrato con el backend pasa a ser **OpenAPI → cliente TypeScript generado**. Mitigante: CLAUDE.md regla 3 ya exige "API First + OpenAPI", y FastAPI genera el spec nativamente.

### D2 — Despliegue: **servicios gestionados**, con Redis incluido

Se acepta la topología del diagrama, **agregando Redis** (ausente en la propuesta original).

| Componente | Servicio |
|---|---|
| Frontend | Cloudflare (ver D4) |
| API + worker + ai-service | Railway |
| PostgreSQL 16 + pgvector | Aiven |
| Cache y colas | Redis gestionado |
| Archivos | Backblaze B2 |
| Correo | Resend |

**Por qué:** resuelve **RNF-19** (respaldo diario automático), hoy incumplido y listado como deuda en `despliegue.md` §7 y en el README §229. Aiven lo trae nativo.

**Justificación honesta:** se adopta por **tiempo de operación ahorrado**, no por precio. Railway + Aiven + B2 + Resend sumados difícilmente salen más baratos que la VM única con docker-compose que ya está montada; Aiven en particular no es barato para Postgres con pgvector. Con un equipo de 2, el ops ahorrado vale más que la diferencia en la factura — pero el argumento "costo eficiente" del diagrama original no se sostiene y no se usa acá.

### D3 — Identidad: **NO adoptar Auth0/Keycloak todavía**

Es el único punto del diagrama que se rechaza en esta iteración. Se mantiene la estrategia ya especificada: JWT emitido por la propia API + OIDC hacia Microsoft Entra ID y Google cuando lleguen las credenciales.

**Por qué:**

1. El flujo de **Cliente Invitado (A3)** usa RUT + clave dinámica generada por el sistema, mostrada una sola vez, con expiración. El identificador de login es el **RUT, no el email**. Auth0 es email-céntrico; se puede forzar, pero a contrapelo.
2. **Microsoft Entra ID es prioridad** y las *enterprise connections* de Auth0 no están en el tier gratuito — el costo real no es el que sugiere la caja del diagrama.
3. Adoptarlo obliga a re-especificar `sistema-actores-roles-rbac` completo: cambian `users.password_hash`, `refresh_tokens`, `/auth/local/login` y la emisión de claims `tenant_id`/`role` que alimenta el `TenantScopeInterceptor`.
4. "Auth0 / Keycloak" en una misma caja esconde decisiones opuestas: uno es SaaS por usuario activo, el otro es software autogestionado con su propia base de datos — que contradice la tesis de D2.

**Reversible:** si aparece demanda de SSO empresarial que justifique el costo, migrar a un IdP externo es un cambio acotado al módulo `auth/`, no un rediseño. Se revisa como ADR propio.

### D4 — Frontend: **Next.js se mantiene**, desplegado como contenedor

El diagrama dice "React (CDN) — Cloudflare Pages". Se rechaza esa lectura.

**Por qué:** `apps/web` es Next.js 14.2.15 con App Router y `output: 'standalone'` — un servidor Node, no un bundle estático. Llevarlo a Cloudflare Pages exige `next export` (se pierden Server Components y rutas dinámicas) o `@cloudflare/next-on-pages` (fuerza runtime edge, sin varias APIs de Node). Ambas son incompatibles con la configuración actual (`transpilePackages`, `outputFileTracingRoot`, el `NormalModuleReplacementPlugin` que saca el `DevRoleSwitcher` del bundle) y con **60 páginas ya construidas**.

Se despliega como contenedor (Railway o Vercel), con Cloudflare adelante como CDN/WAF. Bajar a SPA estática es posible, pero es una reescritura que necesita su propia justificación.

### D5 — Cajas que faltaban en el diagrama

Se incorporan tres omisiones de la propuesta original:

1. **Redis + worker/scheduler.** El core del producto es avisar vencimientos. Sin cola ni cron no hay quién dispare `notification_rules` ni `norm_sync_runs` contra BCN. Con backend en Python: **ARQ o Celery** sobre Redis (BullMQ deja de aplicar).
2. **`apps/ai-service`.** pgvector estaba en la DB sin nada que lo consuma: el chatbot (S-34/S-35), el RAG sobre `legal_articles` y los 4 agentes del análisis de actores no tenían host.
3. **Google Drive / OneDrive.** `integration_accounts` y `document_versions.storage_provider` contemplan que los documentos del cliente vivan en *su* Drive. El diagrama solo tenía B2.

### D6 — RNF de capacidad (nuevo)

Para cerrar la objeción del encargado con datos en vez de opiniones, se propone como requisito verificable:

> **RNF-30:** 500 usuarios concurrentes con p95 < 500 ms en listados paginados y 99,5 % de disponibilidad mensual en horario hábil CLT.

Se valida con una prueba de carga contra el entorno de staging antes del primer contrato pagado, y se repite ante cada cambio de infraestructura.

---

## Topología resultante

```
                            Internet
                               │
                  ┌────────────▼─────────────┐
                  │  Cloudflare (CDN + WAF)  │
                  └────────────┬─────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  apps/web           │  Next.js 14 (contenedor)
                    │  Server Components  │
                    └──────────┬──────────┘
                               │ HTTPS · JWT en Authorization
                    ┌──────────▼──────────┐        ┌────────────────────┐
                    │  apps/api           │───────▶│  apps/ai-service   │
                    │  FastAPI (Railway)  │  HTTP  │  FastAPI+LangGraph │
                    │  OpenAPI nativo     │◀───────│  RAG sobre pgvector│
                    └───┬────┬────┬───┬───┘        └─────────┬──────────┘
                        │    │    │   │                      │
        ┌───────────────┘    │    │   └──────────┐           │
        │                    │    │              │           │
┌───────▼────────┐  ┌────────▼──┐ │      ┌───────▼──────┐    │
│ PostgreSQL 16  │◀─┼───────────┼─┼──────┼──────────────┼────┘
│ + pgvector     │  │  Redis    │ │      │ Backblaze B2 │
│ (Aiven)        │  │  cache +  │ │      │  evidencia   │
│ RLS por tenant │  │  colas    │ │      └───────▲──────┘
│ backup diario  │  └────┬──────┘ │              │
└────────────────┘       │        │              │ URL firmada
                    ┌────▼──────┐ │              │ (subida directa
                    │apps/worker│ │              │  desde navegador)
                    │ARQ/Celery │ │         ┌────┴─────┐
                    │vencimientos│ │        │ apps/web │
                    │sync BCN   │ │         └──────────┘
                    └────┬──────┘ │
                         │        │
                    ┌────▼────┐   └──▶ Google Drive / OneDrive
                    │ Resend  │        (integration_accounts)
                    └─────────┘
```

**Cambios respecto al diagrama original:** se agregan Redis, `apps/worker`, `apps/ai-service` y las integraciones Drive/OneDrive; la caja de identidad externa se retira (D3); el frontend deja de ser CDN estático (D4).

---

## Consecuencias

### ✅ Positivas
- Cierra RNF-19 (backups diarios) sin trabajo propio — es deuda abierta desde el inicio del proyecto
- Un solo lenguaje para api + worker + ai-service, con un equipo de 2 personas
- FastAPI genera el contrato OpenAPI nativamente, que CLAUDE.md regla 3 ya exigía
- Los binarios nunca pasan por la API (URL firmada), alineado con la decisión del modelo de datos ("binarios fuera de PostgreSQL")
- Cierra ADR-002, que llevaba dos meses en `Propuesto` contradiciendo al código

### ⚠️ Trade-offs
- **Se pierde Zod compartido** entre frontend y backend; se reemplaza por codegen desde OpenAPI (un paso más de build, y un momento donde los tipos pueden quedar desincronizados si el pipeline falla en silencio)
- Se descarta el NestJS existente. Poco código, pero incluye la validación de entorno, los health checks y `strict: true` que hay que rehacer en Python
- `docs/development/despliegue.md` (runbook docker-compose + Caddy) y `docker-compose.prod.yml` quedan obsoletos
- Dependencia de 5 proveedores externos: cada uno es un punto de falla y un contrato que alguien debe administrar
- El costo mensual probablemente **sube** respecto de la VM actual

### 🔄 Neutral
- El modelo de datos no cambia — es agnóstico del lenguaje de la API
- `packages/shared` sigue sirviendo al frontend; solo deja de ser el contrato con el backend
- docker-compose sigue siendo válido para desarrollo local

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| **Archivos huérfanos en B2.** El paso "el frontend notifica que la carga terminó" depende de que el navegador cumpla. Si se cierra la pestaña: archivo sin metadata. Si miente: metadata sin archivo | `document_versions` necesita un campo de estado (`pending` → `confirmed`) que **el modelo de datos actual no tiene**. Más verificación server-side (event notification de B2, o `HEAD` antes de confirmar) y un job de reconciliación en el worker |
| **Fuga de tenants por connection pooling.** Si Railway/Aiven interponen PgBouncer, un `SET` de sesión filtraría el `tenant_id` entre requests | El diseño usa `SET LOCAL app.current_tenant_id` **dentro de la transacción**, que sí es seguro en modo *transaction*. Queda documentado acá para que nadie lo "optimice" a nivel de sesión |
| **URL firmada sin validación de tenant.** RLS no cubre el object storage | La ruta del objeto en B2 debe incluir el `tenant_id`, y la URL se emite solo tras validar pertenencia. Expiración corta, también en descarga |
| **Residencia de datos.** Se almacenarán RUTs, datos de trabajadores y evidencia de cumplimiento de empresas chilenas; el análisis de actores ya cita la **Ley 21.719** | Confirmar región de Aiven y B2 **antes** del primer contrato pagado. No es bloqueador, es una pregunta con respuesta |
| Codegen OpenAPI se desincroniza y nadie lo nota | El paso de generación corre en CI y falla el build si el cliente generado difiere del versionado |

---

## Alternativas consideradas

| Alternativa | Por qué no se elige |
|---|---|
| Mantener NestJS + TypeScript en la API | Conserva Zod end-to-end, pero obliga a dos lenguajes con un equipo de 2, y deja el procesamiento de XML/PDF/RAG en el ecosistema más débil para esa tarea |
| Fastify + tRPC (ADR-002) | Nunca se implementó; el repo tiene NestJS. tRPC además choca con "API-first + OpenAPI" de CLAUDE.md regla 3, porque el contrato deja de ser consumible por terceros |
| Seguir en VM única con docker-compose | Es lo que hay y funciona, pero RNF-19 sigue incumplido y el ops recae en un equipo de 2 |
| Adoptar Auth0 ahora | Ver D3: el flujo de Cliente Invitado es RUT-céntrico y custom, y Entra ID no está en el tier gratuito |
| Frontend como SPA estática en Cloudflare Pages | Ver D4: reescritura de 60 páginas ya construidas sobre App Router |

---

## Preguntas abiertas que bloquean la aprobación

| # | Pregunta | Para quién |
|---|---|---|
| 1 | ¿"Api Fast" en la propuesta es FastAPI (Python) o Fastify (Node)? Todo este ADR asume lo primero | Mentor senior |
| 2 | ¿El "React (CDN)" del diagrama implica bajar Next.js a SPA, o era una simplificación? | Mentor senior |
| 3 | ¿Qué región de Aiven y B2, dada la Ley 21.719? | Mentor senior · encargado |
| 4 | ¿Se acepta RNF-30 como meta de capacidad, o el encargado tiene otro número en mente? | Encargado |
| 5 | ¿Quién administra las cuentas de los 5 proveedores y con qué presupuesto mensual techo? | Encargado |

---

## Criterios de revisión

Revisar este ADR si:
- Aparece demanda de SSO empresarial (Entra ID por cliente) que justifique el costo de un IdP gestionado → reevaluar D3
- El equipo crece a 4+ personas → el argumento de "un solo lenguaje" pierde peso; podría convenir volver a TypeScript en la API por el ecosistema de frontend
- La prueba de carga de RNF-30 falla → el problema estará en PostgreSQL o en el servicio IA, no en el framework; dimensionar ahí antes de tocar el stack
- El costo mensual de los servicios gestionados supera el techo definido en la pregunta abierta #5 → reevaluar D2 contra VM propia

---

## Referencias
- Estado real del backend: `docs/arquitectura/backend-arquitectura.md`
- ADR que este documento reemplaza: `adr/ADR-002-backend-separado.md`
- Spec de auth y RBAC afectada por D3: `openspec/changes/sistema-actores-roles-rbac/design.md`
- Modelo de datos (propuesta del mentor, 47 tablas): `modelo_preliminar_PostgreSQL.xlsx` — pendiente de consolidar en `docs/arquitectura/diagrama-base-datos.md`, hoy vacío
- Runbook que queda obsoleto con D2: `docs/development/despliegue.md`
