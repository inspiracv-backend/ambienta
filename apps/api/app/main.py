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
from sqlalchemy.orm import Session

from .config import get_settings
from .db import check_database, get_db

settings = get_settings()

app = FastAPI(
    title="Ambienta API",
    version="0.1.0",
    description="Backend de gestion de cumplimiento ambiental.",
)

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
def health_db(response: Response, db: Session = Depends(get_db)) -> dict:
    """Readiness: la base responde y el esquema esta cargado."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", **check_database()}
    except Exception as exc:  # noqa: BLE001 — el health reporta cualquier fallo
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "connected": False, "detail": str(exc)}


from .routers import (
    audits, catalog, compliance, dashboard, documents, facilities,
    iso14001, notifications, obligations, support, system, tenants, users,
)

api_v1_prefix = "/api/v1"
app.include_router(dashboard.router, prefix=api_v1_prefix)
app.include_router(tenants.router, prefix=api_v1_prefix)
app.include_router(facilities.router, prefix=api_v1_prefix)
app.include_router(users.router, prefix=api_v1_prefix)
app.include_router(obligations.router, prefix=api_v1_prefix)
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
