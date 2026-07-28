# Ambienta

**Sistema multi-tenant de gestión de cumplimiento ambiental para empresas industriales en Chile y Latam.**

Ambienta ayuda a las empresas a gestionar vencimientos, obligaciones regulatorias (RETC, Ley REP, SINADER, SIDREP, DAE, etc.), evidencias y no conformidades de forma centralizada, reduciendo el riesgo de multas y el trabajo manual.

---

## Estado del proyecto

| Componente | Estado |
|---|---|
| **Frontend** (`apps/web`) | 15 de 16 secciones implementadas y verificadas, **con datos mock en memoria** (no consume la API todavía) |
| **API** (`apps/api`) | Arranca, con configuración validada y health checks. **Sin** módulos de negocio, ORM ni auth |
| **PostgreSQL + pgvector · Redis** | Operativos en ambos entornos |
| **Modelo de datos y RBAC** | Especificado en `openspec/`, **pendiente de aprobación** |
| **Worker · AI Service** | Placeholders, no implementados |

El backend de negocio no está implementado por diseño: [CLAUDE.md](./CLAUDE.md) establece Spec-Driven Development como regla no negociable — primero se aprueba la spec, después se implementa. La propuesta del sistema de actores/roles/RBAC está redactada y espera revisión: [`openspec/changes/sistema-actores-roles-rbac/`](./openspec/changes/sistema-actores-roles-rbac/).

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | Next.js 14.2 (App Router) + TypeScript + Tailwind |
| API | NestJS 10 + Express |
| Worker | Node.js + BullMQ *(no implementado)* |
| Servicio IA | Python + FastAPI + LangGraph *(no implementado)* |
| Base de datos | PostgreSQL 16 + pgvector 0.8 |
| Cache / Colas | Redis 7 |
| Monorepo | npm workspaces + Turborepo |
| Validación | Zod (compartido entre web y api vía `packages/shared`) |
| Infraestructura | Docker + Docker Compose · Caddy (TLS automático) |
| Autenticación | JWT + Microsoft Entra ID (prioridad) + Google *(pendiente de credenciales)* |
| Email | Resend *(no implementado)* |
| Metodología | Spec-Driven Development (OpenSpec) |

> **Nota histórica:** versiones anteriores de este README describían Fastify + tRPC + Drizzle + CASL + pnpm. El código real nunca fue eso. La tabla de arriba refleja el repositorio tal como está. Ver [auditoría de stack](./docs/arquitectura/backend-arquitectura.md#2-stack-real-vs-el-documentado-históricamente).

---

## Estructura del monorepo

```
ambienta/
├── apps/
│   ├── web/                  # Frontend (Next.js) — implementado con mocks
│   ├── api/                  # API (NestJS) — infraestructura lista
│   ├── ai-service/           # Servicio de IA — placeholder
│   └── worker/               # Worker de notificaciones — placeholder
├── packages/
│   └── shared/               # Schemas Zod compartidos (fuente de verdad de tipos)
├── infra/
│   ├── postgres/init/        # Extensiones y schemas iniciales
│   └── caddy/Caddyfile       # Reverse proxy de producción
├── docs/
│   ├── arquitectura/         # ADD, ADRs, arquitectura del backend
│   └── development/          # Entornos y runbook de despliegue
├── openspec/
│   ├── analisis/             # Análisis funcional por sección
│   └── changes/              # Propuestas (proposal → design → tasks)
├── docker-compose.yml        # Entorno de DESARROLLO
├── docker-compose.prod.yml   # Entorno de PRODUCCIÓN
└── .env.example              # Plantilla de variables de entorno
```

---

## Entornos

### Desarrollo — local

```bash
docker compose up -d
```

No requiere `.env`: el Compose ya trae credenciales locales. La primera vez tarda unos minutos (descarga de imágenes + instalación de dependencias).

| Servicio | URL |
|---|---|
| **Frontend** | http://localhost:3000 |
| **API** | http://localhost:3001/api/v1 |
| Health (liveness) | http://localhost:3001/health |
| Health (readiness) | http://localhost:3001/health/ready |
| PostgreSQL | `postgresql://ambienta:ambienta_dev@localhost:5432/ambienta` |
| Redis | `redis://localhost:6379` |

Verificar que quedó bien:

```bash
curl http://localhost:3001/health/ready
```

Debe responder `"estado": "ok"` con `postgres` y `redis` en `ok`.

### Producción — servidor

```bash
cp .env.example .env    # completar con valores reales
docker compose -f docker-compose.prod.yml up -d --build
```

| Servicio | URL |
|---|---|
| **Frontend** | `https://<DOMAIN_WEB>` |
| **API** | `https://<DOMAIN_API>/api/v1` |
| Health | `https://<DOMAIN_API>/health` |
| PostgreSQL · Redis | Sin exposición pública (solo red interna Docker) |

Los dominios se definen en `.env` (`DOMAIN_WEB`, `DOMAIN_API`) y **deben resolver por DNS al servidor antes del primer arranque**, porque Let's Encrypt valida el dominio por HTTP para emitir el certificado.

> **No hay un despliegue de producción activo todavía.** La infraestructura está lista y validada, pero no existe un servidor aprovisionado ni un dominio configurado, así que no hay una URL pública que compartir. Cuando se aprovisione, las URLs serán las de la tabla con los dominios reales.

Procedimiento completo, verificación y rollback: **[runbook de despliegue](./docs/development/despliegue.md)**.

### Diferencias entre entornos

| | Desarrollo | Producción |
|---|---|---|
| TLS | No (HTTP) | Sí, automático (Caddy + Let's Encrypt) |
| Postgres / Redis | Expuestos en localhost | Solo red interna (`internal: true`) |
| Redis | Sin contraseña | Con contraseña + persistencia AOF |
| Recarga de código | Hot reload | Imagen inmutable |
| Usuario del contenedor | root | No-root (uid 1001) |
| Secretos | En el Compose, en claro | En `.env`, fuera de git |

Detalle completo en **[guía de entornos](./docs/development/entornos.md)**.

---

## Comandos útiles

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

# Sin Docker (solo las bases en contenedor)
docker compose up -d postgres redis
npm install
npm run dev --workspace @ambienta/web

# Calidad
npm run typecheck --workspace @ambienta/api
npm run lint --workspace @ambienta/web
```

---

## Documentación

| Documento | Contenido |
|---|---|
| [Arquitectura del backend](./docs/arquitectura/backend-arquitectura.md) | Estado real, stack, topología, health checks, seguridad multi-tenant |
| [Guía de entornos](./docs/development/entornos.md) | Dev y producción en detalle, problemas frecuentes |
| [Runbook de despliegue](./docs/development/despliegue.md) | Paso a paso, verificación, rollback, diagnóstico |
| [Análisis funcional por sección](./openspec/analisis/) | Elementos visuales, RF, gaps y heurísticas de cada pantalla |
| [Propuestas OpenSpec](./openspec/changes/) | Specs pendientes de aprobación |
| [CLAUDE.md](./CLAUDE.md) | Reglas no negociables de desarrollo |

---

## Principios de desarrollo

1. **Spec-Driven Development** → primero se especifica y aprueba, después se implementa.
2. **Backend separado** → frontend y API completamente desacoplados.
3. **Multi-tenant fuerte** → aislamiento por `tenant_id` + Row Level Security como segunda barrera.
4. **RBAC en la API, siempre** → los condicionales por rol del frontend son cosméticos, nunca la barrera real.
5. **Una sola fuente de verdad de tipos** → schemas Zod en `packages/shared`, consumidos por web y api.
6. **API-first** → el backend puede ser consumido por web, móvil o integraciones.

---

## Deuda técnica conocida

Documentada explícitamente para que no se asuma resuelta:

1. **ADR-002 sigue en estado "Propuesto"** y describe un stack (Fastify + tRPC + Drizzle) que el código contradice. Requiere decisión del equipo.
2. **Sin backups automáticos** — RNF-19 exige respaldo diario. Ver §7 del runbook.
3. **Sin CI/CD** — el despliegue es manual por SSH.
4. **Sin observabilidad** — logs a stdout, sin agregación ni alertas.
5. **Credenciales OAuth pendientes** — el login social está deshabilitado y devuelve 501 hasta configurarlas.
6. **El frontend no consume la API** — toda la persistencia es mock en memoria, por sesión de navegador.

---

## Equipo

Luciano Recchini Studio · Fabrizzio Gomez · Gabriel Tovar

---

*Ambienta — Cumplimiento ambiental, sin el caos.*
