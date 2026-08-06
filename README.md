# Ambienta

**Sistema multi-tenant de gestion de cumplimiento ambiental para empresas industriales en Chile y Latam.**

Ambienta ayuda a las empresas a gestionar vencimientos, obligaciones regulatorias (RETC, Ley REP, SINADER, SIDREP, DAE, etc.), evidencias y no conformidades de forma centralizada, reduciendo el riesgo de multas y el trabajo manual.

---

## Estado del proyecto

| Componente | Estado |
|---|---|
| **Frontend** (`apps/web`) | 39 paginas, 20+ organismos Atomic Design, 13 stores conectados a la API real |
| **API** (`apps/api`) | FastAPI con 12 routers, 93 endpoints, servicios de logica de negocio, RLS activo |
| **Base de datos** (`db/`) | PostgreSQL 16 + pgvector, 51 tablas, 37 RLS policies, seed data |
| **packages/shared** | Schemas Zod compartidos: user, tenant, obligation, audit, legal-norm, y 6 mas |
| **Worker** (`apps/worker`) | Placeholder, no implementado |
| **AI Service** (`apps/ai-service`) | Placeholder, no implementado |

---

## Stack tecnologico

| Capa | Tecnologia |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind |
| API | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| Worker | Python + Celery/ARQ *(no implementado)* |
| Servicio IA | Python + FastAPI + LangGraph *(no implementado)* |
| Base de datos | PostgreSQL 16 + pgvector 0.8 |
| Monorepo | npm workspaces |
| Validacion | Zod (frontend) + Pydantic (backend) via `packages/shared` |
| Infraestructura | Docker + Docker Compose |
| Autenticacion | Clerk *(ADR-006 aprobado, integracion pendiente)* |
| Email | Resend *(no implementado)* |
| Metodologia | Spec-Driven Development (OpenSpec) |

---

## Estructura del monorepo

```
ambienta/
├── apps/
│   ├── web/                  # Frontend (Next.js) — 39 paginas, stores conectados a API
│   ├── api/                  # API (FastAPI) — 12 routers, 93 endpoints, RLS
│   ├── ai-service/           # Servicio de IA — placeholder
│   └── worker/               # Worker de notificaciones — placeholder
├── packages/
│   └── shared/               # Schemas Zod compartidos (fuente de verdad de tipos)
├── db/
│   ├── 01_schema.sql         # 51 tablas con RLS y triggers
│   ├── 02_seed.sql           # Datos demo (2 tenants, 5 usuarios, facilities)
│   ├── 02_smoke_test.sql     # Tests de aislamiento y constraints
│   └── 03_seed_catalogos.sql # Paises, normas, permisos, sectores CIIU
├── infra/
│   ├── postgres/init/        # Extension pgvector
│   └── caddy/Caddyfile       # Reverse proxy de produccion
├── docs/
│   ├── arquitectura/         # ADRs y arquitectura
│   └── development/          # Entornos y runbook
├── openspec/
│   ├── analisis/             # Analisis funcional por seccion
│   ├── changes/              # Propuestas (proposal + design + tasks)
│   └── templates/            # Templates de propuesta y diseno
├── docker-compose.yml        # Entorno de DESARROLLO
├── docker-compose.prod.yml   # Entorno de PRODUCCION
└── .env.example              # Plantilla de variables de entorno
```

---

## Entornos

### Desarrollo — local

```bash
docker compose up -d
```

No requiere `.env`: el Compose ya trae credenciales locales. La primera vez tarda unos minutos (descarga de imagenes + instalacion de dependencias).

| Servicio | URL |
|---|---|
| **Frontend** | http://localhost:3000 |
| **API** | http://localhost:8000/api/v1 |
| **Swagger** | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| PostgreSQL | `postgresql://ambienta:ambienta_dev@localhost:5432/ambienta` |

Verificar que quedo bien:

```bash
curl http://localhost:8000/health
```

#### Entrar como cada rol (solo en desarrollo)

No hay autenticacion real todavia: la pantalla de login muestra un panel **Acceso rapido de desarrollo** (DevRoleSwitcher) con los usuarios de la base de datos. Al hacer login, el frontend carga los datos reales del tenant correspondiente via la API.

| Rol | Descripcion |
|---|---|
| Superadmin | Plataforma completa (gestion de tenants) |
| Admin Empresa | Gestiona su empresa y empleados |
| Usuario Interno | Operativo — crea/envia declaraciones |
| Gestor | Admin Empresa + modulo de cartera de clientes |
| Cliente Invitado | Solo sus tickets de soporte |

El DevRoleSwitcher **no existe en builds de produccion**: se elimina cuando exista auth real con Clerk.

#### Seguridad multi-tenant

Cada request a la API incluye un header `X-Tenant-Id`. El middleware de FastAPI (`deps.py`):

1. Ejecuta `SET LOCAL ROLE ambienta_app` para bajar de superuser al rol restringido
2. Ejecuta `set_config('ambienta.tenant_id', :tid, true)` para activar RLS

Las 37 politicas RLS garantizan que un tenant nunca ve datos de otro, incluso si hay un bug en la aplicacion.

### Produccion — servidor

```bash
cp .env.example .env    # completar con valores reales
docker compose -f docker-compose.prod.yml up -d --build
```

> **No hay un despliegue de produccion activo todavia.** La infraestructura esta lista y validada, pero no existe un servidor aprovisionado.

Procedimiento completo, verificacion y rollback: **[runbook de despliegue](./docs/development/despliegue.md)**.

---

## Comandos utiles

```bash
# Desarrollo
docker compose up -d                  # levantar todo
docker compose logs -f api            # seguir logs de la API
docker compose ps                     # estado de los servicios
docker compose down                   # detener (conserva datos)
docker compose down -v                # detener y BORRAR la base de datos
docker compose up -d --build api      # reconstruir tras cambiar dependencias

# Base de datos
docker compose exec postgres psql -U ambienta -d ambienta

# Sin Docker (bases en contenedor, app local)
docker compose up -d postgres
npm install
npm run dev:web                       # Next.js en :3000

# API local (requiere Python 3.12+)
cd apps/api && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## Documentacion

| Documento | Contenido |
|---|---|
| [CLAUDE.md](./CLAUDE.md) | Reglas no negociables de desarrollo |
| [ADR-005: Stack y despliegue](./docs/arquitectura/adr/ADR-005-stack-y-despliegue.md) | Decisiones de tecnologia |
| [ADR-006: Autenticacion Clerk](./docs/arquitectura/adr/ADR-006-autenticacion-clerk.md) | Proveedor de auth elegido |
| [Analisis funcional por seccion](./openspec/analisis/) | Requisitos, gaps y heuristicas de cada pantalla |
| [Propuestas OpenSpec](./openspec/changes/) | 4 specs (3 aprobadas, 1 pendiente) |
| [Guia de entornos](./docs/development/entornos.md) | Dev y produccion en detalle |
| [Runbook de despliegue](./docs/development/despliegue.md) | Paso a paso, verificacion, rollback |

---

## Principios de desarrollo

1. **Spec-Driven Development** — primero se especifica y aprueba, despues se implementa.
2. **Backend separado** — frontend y API completamente desacoplados.
3. **Multi-tenant fuerte** — aislamiento por `tenant_id` + Row Level Security como segunda barrera.
4. **RBAC en la API, siempre** — los condicionales por rol del frontend son cosmeticos, nunca la barrera real.
5. **Una sola fuente de verdad de tipos** — schemas Zod en `packages/shared`, Pydantic en la API.
6. **API-first** — el backend puede ser consumido por web, movil o integraciones.

---

## Deuda tecnica conocida

1. **Sin CI/CD** — el despliegue es manual. GitHub Actions pendiente (#86).
2. **Sin backups automaticos** — RNF-19 exige respaldo diario.
3. **Sin observabilidad** — logs a stdout, sin agregacion ni alertas.
4. **Auth mock** — login sin JWT ni Clerk. ADR-006 aprobado, integracion pendiente (#91).
5. **Migraciones no versionadas** — el schema SQL es la fuente de verdad, sin Alembic (#52).
6. **Dashboard usa mocks** — propuesta OpenSpec para conectar a API real pendiente de aprobacion (ABA-64).

---

*Ambienta — Cumplimiento ambiental, sin el caos.*
