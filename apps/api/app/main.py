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
from .seguridad_http import CabecerasDeSeguridad
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, check_database
from .errores import manejar_error_de_integridad
from .deps import (
    exigir_perfil_de_empresa_completo,
    exigir_permiso_de_la_ruta,
    get_admin_db,
)
from .openapi import DESCRIPCION, TAGS_METADATA, construir_esquema
from .services.auditoria_automatica import instalar as instalar_auditoria
from .routers import (
    acceso_invitado,
    audits, catalog, compliance, contratos, dashboard, declaraciones, departments,
    crm,
    documents,
    facilities,
    identidad,
    integraciones, iso14001, notifications, obligations, permisos, processes, support, system,
    plantillas, roles, tenants,
    users, webhooks,
)

settings = get_settings()

# El registro de actividades se engancha al `flush` de la sesion, una sola vez
# al importar la aplicacion. **Sin esto `audit_log` queda vacia** y nada lo
# advierte: los endpoints siguen respondiendo 200 y la rotacion mensual rota
# una tabla sin filas. Es exactamente lo que pasaba hasta hoy.
instalar_auditoria(SessionLocal)

app = FastAPI(
    title="Ambienta API",
    version="0.1.0",
    description=DESCRIPCION,
    openapi_tags=TAGS_METADATA,
)

# ── Guarda de permisos, una sola vez para toda la API ─────────────────────
#
# Va aca y no endpoint por endpoint porque son mas de 150 escrituras: ponerlo a
# mano es una decision que se puede olvidar, y **olvidarla no falla** — deja el
# endpoint abierto y nadie se entera. Es el mismo motivo por el que el 401 y el
# 404 del contrato OpenAPI se derivan de la ruta en vez de escribirse.
#
# Que permiso exige cada ruta lo decide `permisos_de_rutas.py`. Las rutas sin
# sesion —`/health`, el webhook de Clerk— quedan fuera porque su raiz esta
# declarada como exenta, no porque la guarda las saltee por accidente.

# El contrato se arma en `openapi.py`: FastAPI describe los caminos felices y
# calla los errores, y un contrato que no dice como falla obliga a descubrirlo
# probando.
app.openapi = lambda: construir_esquema(app)

# Una restriccion violada es un dato malo del cliente, no una falla del
# servidor. Sin este manejador sale 500 y quien llama no sabe que corregir.
app.add_exception_handler(IntegrityError, manejar_error_de_integridad)

# **Se agrega antes que CORS a proposito.** Starlette ejecuta los middleware en
# orden inverso al de registro, asi que este queda por fuera y sus cabeceras
# alcanzan tambien a las respuestas que genera CORS por su cuenta —el rechazo
# de un preflight, por ejemplo— que de otro modo saldrian sin proteger.
app.add_middleware(CabecerasDeSeguridad)

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
# El webhook NO lleva la guarda: quien llama es Clerk, no un usuario. No hay
# sesion de la cual sacar permisos, y colgarsela lo haria fallar con 401
# antes siquiera de verificar la firma HMAC.
app.include_router(webhooks.router, prefix=api_v1_prefix)
# `/me` va sin guarda de permiso a proposito: preguntar que puedo hacer no
# puede exigir poder hacer algo. Ver `SIN_GUARDA_DE_PERMISO` en
# `permisos_de_rutas.py`, donde queda escrito el motivo.
app.include_router(identidad.router, prefix=api_v1_prefix)
# El acceso del Cliente Invitado va **sin `exigir_permiso_de_la_ruta`**, igual
# que el webhook y por el mismo motivo estructural: quien llama no tiene sesion
# de la cual sacar permisos. Un invitado no tiene rol. Lo que lo acota no es una
# lista de permisos sino que **estos tres endpoints son todo lo que puede
# tocar** — ver el docstring del router.
app.include_router(acceso_invitado.router, prefix=api_v1_prefix)
app.include_router(dashboard.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(tenants.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(facilities.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(contratos.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(users.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(roles.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(departments.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(processes.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(integraciones.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(
    obligations.router,
    prefix=api_v1_prefix,
    dependencies=[
        Depends(exigir_permiso_de_la_ruta),
        # RF-10: el Admin Empresa no opera esto sin el perfil completo.
        # **Solo estas dos familias** — es el texto literal del
        # requisito, y ampliarlo bloquearia trabajo que el requisito no
        # pidio bloquear.
        Depends(exigir_perfil_de_empresa_completo),
    ],
)
app.include_router(declaraciones.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(plantillas.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(audits.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(catalog.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(permisos.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(
    compliance.router,
    prefix=api_v1_prefix,
    dependencies=[
        Depends(exigir_permiso_de_la_ruta),
        # RF-10: el Admin Empresa no opera esto sin el perfil completo.
        # **Solo estas dos familias** — es el texto literal del
        # requisito, y ampliarlo bloquearia trabajo que el requisito no
        # pidio bloquear.
        Depends(exigir_perfil_de_empresa_completo),
    ],
)
app.include_router(documents.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(crm.router, prefix=api_v1_prefix)
app.include_router(iso14001.router, prefix=api_v1_prefix)
app.include_router(notifications.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(support.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])
app.include_router(system.router, prefix=api_v1_prefix, dependencies=[Depends(exigir_permiso_de_la_ruta)])


@app.get("/api/v1", tags=["meta"])
def api_root() -> dict:
    """Raiz de la API versionada. Los routers de dominio cuelgan de aca."""
    return {"api": "ambienta", "version": "v1"}
