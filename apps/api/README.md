# @ambienta/api — Backend FastAPI

Backend de Ambienta en **FastAPI (Python 3.12)**. Reemplaza el scaffold NestJS
previo (que no tenía lógica de negocio). Decisión de stack tomada el 3-ago-2026.

Hoy expone **93 endpoints** repartidos en 12 routers de dominio.

## Correr

Lo normal es levantarlo con el resto vía Docker desde la raíz del repo:

```bash
docker compose up
```

- API: http://localhost:8000
- Health: http://localhost:8000/health
- Health BD: http://localhost:8000/health/db
- OpenAPI (Swagger UI): http://localhost:8000/docs

Standalone, sin Docker:

```bash
cd apps/api
python -m venv .venv && .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
cd apps/api
pip install -r requirements-dev.txt
python -m pytest
```

Los tests de autenticación **no necesitan cuenta de Clerk**: `tests/conftest.py`
genera un par RSA propio y sirve su parte pública como si fuera la JWKS de
Clerk. Así se pueden firmar tokens válidos, expirados o incompletos sin red y
sin credenciales.

## Estructura

| Ruta | Qué hace |
|---|---|
| `app/main.py` | App FastAPI, CORS, health y registro de los 12 routers |
| `app/config.py` | Configuración leída del entorno (pydantic-settings) |
| `app/db.py` | Motor y sesión de SQLAlchemy |
| `app/auth.py` | **Validación del JWT de Clerk. Único archivo acoplado al proveedor** |
| `app/deps.py` | Dependencias compartidas: sesión, identidad y sesión con RLS |
| `app/models/` | Modelos SQLAlchemy de las 51 tablas |
| `app/schemas/` | Schemas Pydantic (entrada/salida de la API) |
| `app/crud/` | Operaciones de lectura y escritura por dominio |
| `app/services/` | Lógica de negocio (cumplimiento, obligaciones, …) |
| `app/routers/` | Un router por dominio |
| `tests/` | Suite de pytest |

## Autenticación (ADR-006: Clerk)

La API **no emite tokens propios**. Clerk autentica; nosotros verificamos.

```
Clerk ──JWT RS256──> Next.js ──Authorization: Bearer──> FastAPI ──verifica con JWKS
                                                            │
                                                     tenant_id del claim firmado
                                                            │
                                                     SET LOCAL + RLS
```

`app/auth.py` valida la firma **localmente** contra la JWKS pública de Clerk,
cacheada una hora en memoria. No se usa el SDK de Clerk a propósito: el SDK
llama a la API de Clerk en cada request, lo que agrega latencia y hace que la
API deje de funcionar si Clerk tiene una caída.

### Dos modos, gobernados por una sola variable

| `CLERK_JWKS_URL` | Modo | Cómo se identifica el tenant |
|---|---|---|
| vacía | Desarrollo | Header `X-Tenant-Id` (el DevRoleSwitcher del frontend) |
| puesta | Producción | Claim `tenant_id` de un JWT firmado. El header se ignora |

Es una sola variable y no un flag por endpoint a propósito: 93 endpoints con
criterios distintos serían 93 formas de dejar un hueco. Con `CLERK_JWKS_URL`
puesta no queda ningún camino que acepte un tenant sin firmar.

### Códigos de respuesta

| Situación | Código | Por qué |
|---|---|---|
| Token válido | 200 | — |
| Token expirado, mal firmado o de otro emisor | 401 | Hay que volver a autenticarse |
| Token sin claim `tenant_id` | 401 | Falta configurar el JWT Template en Clerk |
| Sin token, con Clerk activo | 401 | — |
| JWKS inaccesible y sin caché | **503** | El token puede estar bien; es la API la que no puede comprobarlo. Un 401 mandaría a re-loguearse a gente cuya sesión es válida |

Si Clerk deja de responder pero hay una copia en caché —aunque esté vencida— se
usa: una llave de hace dos horas verifica firmas igual de bien, y rechazar a
todos porque el CDN parpadeó sería peor que el riesgo que cubre el TTL.

### Sincronización de usuarios

Clerk avisa por webhook cuando un usuario se crea, cambia o se elimina:

```
POST /api/v1/webhooks/clerk
```

Es el **único endpoint sin JWT**: quien llama es Clerk, no una persona con
sesión. La autenticidad se comprueba con la firma HMAC del payload (protocolo
svix) usando `CLERK_WEBHOOK_SECRET`. Tampoco pasa por RLS — al procesar un
`user.created` todavía no se sabe de qué tenant es la sesión, porque no hay
sesión: el tenant sale del payload firmado.

| Evento | Qué hace |
|---|---|
| `user.created` | Crea la fila. Si ya existe alguien con ese correo **sin** `clerk_id`, lo adopta en vez de duplicar |
| `user.updated` | Actualiza email y nombre. **No pisa** el tenant ni el rol: un cambio de foto en Clerk no debe revertir lo que un admin configuró acá |
| `user.deleted` | `status = 'disabled'`. **No borra la fila**: `audit_log` la referencia, y borrarla dejaría huérfano el historial que RNF-08 exige conservar |
| Cualquier otro | Responde 200 e ignora, para que Clerk no lo reintente indefinidamente |

Un payload firmado pero incompleto (sin `tenant_id` en `publicMetadata`, por
ejemplo) responde **400**, no 500: es auténtico, pero le falta algo que solo se
arregla en el dashboard de Clerk. Con un 5xx, Clerk reintentaría para siempre un
payload que no va a mejorar solo.

## Multi-tenancy y RLS

El esquema (`db/01_schema.sql`) aplica `FORCE ROW LEVEL SECURITY` con 37
políticas. `get_tenant_db()` en `deps.py` abre cada transacción con:

```sql
SET LOCAL ROLE ambienta_app;
SELECT set_config('ambienta.tenant_id', '<uuid>', true);
```

El rol **no** puede ser superusuario o RLS no aplica. Ver `db/README.md`.

`get_tenant_db()` no cambió con la llegada de Clerk, y es deliberado: la capa
que aplica RLS no tiene por qué saber cómo se autenticó el usuario. Recibe un
UUID ya verificado y hace siempre lo mismo. Lo único que cambió es de dónde
sale ese UUID — antes de un header sin firmar, ahora de un claim firmado.

## Contrato API-first

FastAPI genera el OpenAPI en `/openapi.json`. De ahí se derivan los tipos del
frontend — complementa a `packages/shared` (Zod/TS), que el frontend seguirá
usando pero que Python no puede importar.

## Specs

Todo cambio se especifica antes de implementarse (CLAUDE.md §1). Las specs
vigentes que tocan esta app:

- `openspec/changes/integracion-clerk-auth/` — autenticación (Fase 1 hecha)
- `openspec/changes/dashboard-metricas-api/` — endpoint de métricas
- `openspec/changes/hallazgos-auditoria-no-conformidades/` — auditorías
