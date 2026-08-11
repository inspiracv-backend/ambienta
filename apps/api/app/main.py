"""@ambienta/api — backend FastAPI.

Punto de entrada minimo: salud y verificacion de la base. La logica de negocio
(matriz legal, obligaciones, auditorias) se construye encima, un router por
dominio, siguiendo API-first + OpenAPI (CLAUDE.md §3). FastAPI genera el
contrato OpenAPI solo, y de ahi se derivan los tipos del frontend.

Nota sobre el modelo de datos: las tablas NO se crean desde SQLAlchemy con
`Base.metadata.create_all()`. El esquema vive en `db/01_schema.sql` y se aplica
por migracion, porque incluye Row Level Security, triggers y constraints que un
ORM no genera. SQLAlchemy se usa para consultar, no para definir el esquema.
"""
from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .db import check_database
from .errores import manejar_error_de_integridad
from .deps import get_admin_db
from .openapi import DESCRIPCION, TAGS_METADATA, construir_esquema
from .routers import (
    audits, catalog, compliance, contratos, dashboard, declaraciones, departments,
    documents,
    facilities,
    integraciones, iso14001, notifications, obligations, processes, support, system,
    plantillas, tenants,
    users, webhooks,
)

settings = get_settings()

app = FastAPI(
    title="Ambienta API",
    version="0.1.0",
    description=DESCRIPCION,
    openapi_tags=TAGS_METADATA,
)

# El contrato se arma en `openapi.py`: FastAPI describe los caminos felices y
# calla los errores, y un contrato que no dice como falla obliga a descubrirlo
# probando.
app.openapi = lambda: construir_esquema(app)

# Una restriccion violada es un dato malo del cliente, no una falla del
# servidor. Sin este manejador sale 500 y quien llama no sabe que corregir.
app.add_exception_handler(IntegrityError, manejar_error_de_integridad)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness: el proceso responde. No toca la base."""
    return {
        "status": "ok",
        "service": "ambienta-api",
        "environment": settings.environment,
    }


@app.get("/health/db", tags=["health"])
def health_db(response: Response, db: Session = Depends(get_admin_db)) -> dict:
    """Readiness: la base responde y el esquema esta cargado."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", **check_database()}
    except Exception as exc:  # noqa: BLE001 — el health reporta cualquier fallo
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "connected": False, "detail": str(exc)}


api_v1_prefix = "/api/v1"
# Sin dependencia de auth a proposito: quien llama es Clerk, no un usuario con
# sesion, y la autenticidad se comprueba con la firma HMAC del payload.
app.include_router(webhooks.router, prefix=api_v1_prefix)
app.include_router(dashboard.router, prefix=api_v1_prefix)
app.include_router(tenants.router, prefix=api_v1_prefix)
app.include_router(facilities.router, prefix=api_v1_prefix)
app.include_router(contratos.router, prefix=api_v1_prefix)
app.include_router(users.router, prefix=api_v1_prefix)
app.include_router(departments.router, prefix=api_v1_prefix)
app.include_router(processes.router, prefix=api_v1_prefix)
app.include_router(integraciones.router, prefix=api_v1_prefix)
app.include_router(obligations.router, prefix=api_v1_prefix)
app.include_router(declaraciones.router, prefix=api_v1_prefix)
app.include_router(plantillas.router, prefix=api_v1_prefix)
app.include_router(audits.router, prefix=api_v1_prefix)
app.include_router(catalog.router, prefix=api_v1_prefix)
app.include_router(compliance.router, prefix=api_v1_prefix)
app.include_router(documents.router, prefix=api_v1_prefix)
app.include_router(iso14001.router, prefix=api_v1_prefix)
app.include_router(notifications.router, prefix=api_v1_prefix)
app.include_router(support.router, prefix=api_v1_prefix)
app.include_router(system.router, prefix=api_v1_prefix)


@app.get("/api/v1", tags=["meta"])
def api_root() -> dict:
    """Raiz de la API versionada. Los routers de dominio cuelgan de aca."""
    return {"api": "ambienta", "version": "v1"}
