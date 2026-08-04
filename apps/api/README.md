# @ambienta/api — Backend FastAPI

Backend de Ambienta en **FastAPI (Python 3.12)**. Reemplaza el scaffold NestJS
previo (que no tenía lógica de negocio). Decisión de stack tomada el 3-ago-2026.

## Correr

Lo normal es levantarlo con el resto vía Docker desde la raíz del repo:

```bash
docker compose up            # postgres + api + web
```

- API: http://localhost:3001
- Health: http://localhost:3001/health
- Health BD: http://localhost:3001/health/db
- OpenAPI (Swagger UI): http://localhost:3001/docs

Standalone, sin Docker:

```bash
cd apps/api
pip install -r requirements.txt
export DATABASE_URL=postgresql://ambienta:ambienta_dev@localhost:5432/ambienta
uvicorn app.main:app --reload --port 3001
```

## Estructura

| Archivo | Qué hace |
|---|---|
| `app/main.py` | App FastAPI, CORS y endpoints de salud |
| `app/config.py` | Configuración leída del entorno (pydantic-settings) |
| `app/db.py` | Conexión a Postgres y verificación del esquema |
| `requirements.txt` | Dependencias ancladas |

## Multi-tenancy y RLS

El esquema (`db/`) aplica `FORCE ROW LEVEL SECURITY`. Cuando se construyan
endpoints reales, cada transacción debe abrir con:

```sql
SET LOCAL ambienta.tenant_id = '<uuid del tenant de la sesión>';
```

y conectarse con un rol que **no** sea superusuario (`ambienta_app`), o RLS no
aplica. Ver `db/README.md`. Hoy `db.py` usa una conexión simple solo para el
health check; el pool y el `SET LOCAL` van cuando entren los primeros endpoints
de dominio (epic #29).

## Contrato API-first

FastAPI genera el OpenAPI en `/openapi.json`. De ahí se derivan los tipos del
frontend — reemplaza al `packages/shared` (Zod/TS), que el frontend seguirá
usando pero que Python no puede importar.
