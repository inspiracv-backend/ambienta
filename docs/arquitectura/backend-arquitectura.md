# Arquitectura del Backend — Ambienta

**Estado:** infraestructura operativa · lógica de negocio pendiente de spec aprobada
**Última actualización:** 2026-07-28

---

## 1. Panorama honesto del estado actual

Es importante partir por esto porque el README histórico del repo describía un backend que no existe.

| Componente | Estado real |
|---|---|
| `apps/api` (NestJS) | **Arranca y responde.** Tiene configuración validada, health checks y CORS. **Sin** módulos de negocio, **sin** ORM, **sin** esquema de base de datos, **sin** auth. |
| `apps/worker` | Placeholder (`console.log`). No implementado. |
| `apps/ai-service` | Placeholder (`console.log`). El funcional lo describe como Python/FastAPI + LangGraph; hoy es TypeScript vacío. |
| `apps/web` (Next.js) | Funcional pero con **datos mock en memoria** — no consume la API todavía. |
| PostgreSQL + pgvector | **Operativo** en ambos entornos, con extensiones y schema `ai` creados. |
| Redis | **Operativo** en ambos entornos. |
| Esquema de datos (tenants, users, RBAC, audit log) | **Especificado, no implementado** → ver [`openspec/changes/sistema-actores-roles-rbac/`](../../openspec/changes/sistema-actores-roles-rbac/) |

**Por qué la lógica de negocio no está implementada:** CLAUDE.md establece Spec-Driven Development como regla no negociable — "solo implementar Features que tengan spec aprobada en `openspec/`". La propuesta del sistema de actores/roles/RBAC está redactada y espera revisión humana. La infraestructura de este documento es la base sobre la que se construirá.

---

## 2. Stack real (vs. el documentado históricamente)

El README original describía **Fastify + tRPC + Drizzle + CASL + pnpm**. El código real es otro. Esta tabla es la fuente de verdad:

| Capa | Real (en el repo) | Lo que decía el README | Nota |
|---|---|---|---|
| API | **NestJS 10** + Express | Fastify + tRPC | Decisión del usuario (2026-07-27): construir sobre NestJS, que es lo instalado |
| Gestor de paquetes | **npm 10** (workspaces) | pnpm | Existe `package-lock.json`, no `pnpm-lock.yaml` |
| Frontend | **Next.js 14.2.15** | Next.js 15 | — |
| ORM | **Ninguno todavía** | Drizzle | Drizzle es el default propuesto en la spec, sin aprobar |
| RBAC | **Ninguno todavía** | CASL | La spec propone tabla de permisos + asignación, sin CASL |
| Base de datos | **PostgreSQL 16 + pgvector 0.8.5** | igual | ✅ coincide |
| Cache/colas | **Redis 7** | igual | ✅ coincide |
| Validación | **Zod** (env + `packages/shared`) | Zod | ✅ coincide |

`docs/arquitectura/adr/ADR-002-backend-separado.md` sigue en estado **Propuesto** (sin aprobar) y contradice el código real. Es deuda arquitectónica abierta: alguien del equipo debe aprobarlo o reemplazarlo por un ADR que refleje NestJS.

---

## 3. Topología de servicios

```
                        Internet
                            │
                    ┌───────▼────────┐
                    │  Caddy (TLS)   │   :80 / :443   ← solo en producción
                    └───┬────────┬───┘
             app.dominio│        │api.dominio
                    ┌───▼───┐ ┌──▼────┐
                    │  web  │ │  api  │
                    │ :3000 │ │ :3001 │
                    └───────┘ └──┬────┘
                                 │  red interna (sin salida a internet)
                        ┌────────┴─────────┐
                   ┌────▼─────┐      ┌─────▼────┐
                   │ Postgres │      │  Redis   │
                   │  :5432   │      │  :6379   │
                   │ +pgvector│      │          │
                   └──────────┘      └──────────┘
```

En **producción** Postgres y Redis viven en una red Docker marcada `internal: true` y no publican puertos al host: son inalcanzables desde internet. La web tampoco los alcanza — solo la API.

En **desarrollo** sí publican puertos (5432/6379) para poder conectar un cliente SQL local.

---

## 4. Estructura de `apps/api`

```
apps/api/src/
├── main.ts                      # bootstrap: CORS, prefijo global, ValidationPipe, shutdown hooks
├── app.module.ts                # raíz: ConfigModule (validado) + HealthModule
├── config/
│   └── env.validation.ts        # esquema Zod de variables de entorno
└── health/
    ├── health.module.ts
    ├── health.controller.ts     # GET /health · GET /health/ready
    └── health.service.ts        # verifica Postgres y Redis
```

Módulos que se agregarán cuando la spec sea aprobada (ver `design.md` de la propuesta): `auth/`, `tenants/`, `perfil-empresa/`, `users/`, `permissions/`, `invitados/`, `sub-tenancy/`, `audit/`, `common/`.

### Convenciones adoptadas

- **Prefijo global `/api/v1`** para todas las rutas de negocio. Los health checks se **excluyen** a propósito (`/health`, no `/api/v1/health`) para que orquestadores y balanceadores no dependan de la versión de la API.
- **`ValidationPipe` global** con `whitelist: true` y `forbidNonWhitelisted: true`: una propiedad no declarada en el DTO produce error 400 en vez de ignorarse en silencio.
- **`strict: true` en TypeScript.** Se activó al construir esta base (antes estaba en `false`); es código nuevo, así que el costo fue nulo y el beneficio en una capa multi-tenant es alto.
- **Validación de entorno al arranque.** Si falta `DATABASE_URL` o `JWT_SECRET` es menor de 32 caracteres, el proceso no arranca. Preferimos fallar en el arranque con un mensaje claro que descubrirlo a mitad de una request.

---

## 5. Health checks

Dos endpoints con propósitos distintos — la diferencia importa operacionalmente:

### `GET /health` — liveness

```json
{ "estado": "ok", "servicio": "ambienta-api", "timestamp": "...", "uptimeSegundos": 42 }
```

**No consulta dependencias a propósito.** Si Postgres se cae, este endpoint sigue devolviendo 200, porque reiniciar el contenedor de la API no arregla una base de datos caída — solo provocaría un ciclo de reinicios inútil. Es el que usa el `HEALTHCHECK` de Docker.

### `GET /health/ready` — readiness

```json
{
  "estado": "ok",
  "dependencias": {
    "postgres": { "estado": "ok", "latenciaMs": 3 },
    "redis":    { "estado": "ok", "latenciaMs": 1 }
  },
  "timestamp": "..."
}
```

Devuelve **503** si alguna dependencia falla, para que un balanceador saque la instancia de rotación sin matarla. Es el endpoint a usar en un readiness probe de Kubernetes o en un chequeo de despliegue.

> Los clientes de Postgres/Redis del `HealthService` existen **solo** para estos chequeos. No son la capa de datos: el ORM, el esquema y las políticas RLS se definen en la propuesta OpenSpec pendiente. No construir lógica de negocio sobre ese pool.

---

## 6. Variables de entorno

Contrato completo en [`.env.example`](../../.env.example). Resumen:

| Variable | Requerida | Notas |
|---|---|---|
| `NODE_ENV` | no (`development`) | `development` \| `production` \| `test` |
| `PORT` | no (`3001`) | — |
| `DATABASE_URL` | **sí** | URL de PostgreSQL |
| `REDIS_URL` | **sí** | URL de Redis |
| `CORS_ORIGINS` | no (`http://localhost:3000`) | Lista separada por coma |
| `JWT_SECRET` | **sí** | Mínimo 32 caracteres, validado |
| `MICROSOFT_CLIENT_ID` / `_SECRET` | no | Sin ellas, login Microsoft deshabilitado |
| `GOOGLE_CLIENT_ID` / `_SECRET` | no | Sin ellas, login Google deshabilitado |
| `RESEND_API_KEY` | no | Correo transaccional (decisión cerrada #18) |

### OAuth: stub honesto, no roto

Las credenciales de Microsoft/Google son **opcionales a propósito** porque todavía no existen. El comportamiento definido es:

1. La API loguea una **advertencia visible en cada arranque** listando qué proveedor falta.
2. Los endpoints `/auth/{proveedor}/callback` responderán **501 Not Implemented** con un mensaje claro.
3. Nunca se simula un login falso.

Esto evita el peor escenario: que el stub quede olvidado y alguien crea que el SSO funciona.

---

## 7. Seguridad multi-tenant (diseñada, no implementada)

CLAUDE.md exige tres barreras. Estado de cada una:

| Barrera | Estado |
|---|---|
| Filtrar por `tenant_id` en toda consulta | Pendiente (no hay consultas de negocio) |
| Row Level Security en PostgreSQL | **Diseñada** en la spec: interceptor que hace `SET LOCAL app.current_tenant_id`, con políticas que leen `current_setting()` — para que el aislamiento no dependa de que el controller recuerde el `WHERE` |
| RBAC verificado en la API | **Diseñado**: `PermissionsGuard` + tabla `permissions`/`user_permissions` |

El frontend ya tiene condicionales por rol (sidebar, gates de ruta), pero **eso es solo cosmético**: la barrera real es la API. Está documentado así en el propio código del frontend.

Detalle completo, incluyendo el modelo del audit log inmutable y la resolución del caso Gestor↔sub-tenant, en la [propuesta OpenSpec](../../openspec/changes/sistema-actores-roles-rbac/design.md).

---

## 8. Decisiones de infraestructura y su razón

| Decisión | Por qué |
|---|---|
| Imagen `pgvector/pgvector:pg16` en vez de `postgres:16` | Trae la extensión ya compilada; con la oficial habría que compilarla en cada build |
| Contexto de build = raíz del monorepo | npm workspaces necesita el `package-lock.json` completo para resolver dependencias de forma reproducible |
| `npm ci` en vez de `npm install` en Docker | Respeta el lockfile exacto → builds reproducibles |
| Copiar manifests antes del código fuente | Docker reutiliza la capa de `npm ci` cuando cambia solo el código, ahorrando minutos por build |
| `output: 'standalone'` en Next | Imagen final con solo las dependencias efectivamente usadas, no todo el `node_modules` del monorepo |
| Volúmenes anónimos sobre `node_modules` en dev | Evita que los `node_modules` del host (Windows) tapen los del contenedor (Linux), donde los binarios nativos sí son compatibles |
| `dumb-init` como entrypoint | Reenvía SIGTERM correctamente a Node, para que los shutdown hooks cierren las conexiones a Postgres/Redis en vez de dejarlas colgadas |
| Usuario no-root en las imágenes de producción | Si la API se ve comprometida, el atacante no tiene root en el contenedor |
| Caddy en vez de Nginx + certbot | TLS automático vía Let's Encrypt sin cron de renovación ni configuración extra |
| Volumen persistente para los certificados de Caddy | Sin él, cada redeploy re-solicita certificados y Let's Encrypt aplica rate limit (5/semana/dominio) |
| Redis con `--appendonly yes` en producción | Las colas del worker sobreviven un reinicio |
| Red `internal: true` para Postgres/Redis | Inalcanzables desde internet, incluso si el firewall del host está mal configurado |

---

## 9. Lo que falta (deuda explícita)

1. **Aprobar la spec de actores/RBAC** y luego implementarla (esquema, migraciones, auth, guards, audit log, seed).
2. **Resolver ADR-002** — el ADR propone un stack que el código contradice.
3. **Credenciales OAuth** de Microsoft Entra ID y Google.
4. **Conectar `apps/web` a la API real** — hoy usa mocks en memoria; toda la persistencia es por sesión de navegador.
5. **Implementar `apps/worker`** (BullMQ para notificaciones/recordatorios) y **`apps/ai-service`** (Python/FastAPI + LangGraph).
6. **Backups de Postgres** — RNF-19 exige respaldo diario automático; no hay ninguno configurado.
7. **CI/CD** — no hay pipeline; el despliegue es manual (ver el runbook).
8. **Observabilidad** — logs a stdout únicamente; sin agregación, métricas ni alertas.

---

## Referencias

- [Guía de entornos (dev y producción)](../development/entornos.md)
- [Runbook de despliegue](../development/despliegue.md)
- [Propuesta OpenSpec — Sistema de Actores, Roles y RBAC](../../openspec/changes/sistema-actores-roles-rbac/proposal.md)
- [Auditoría de stack del frontend](./auditoria-stack-frontend.md)
