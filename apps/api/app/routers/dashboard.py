"""Metricas agregadas del Dashboard (S-06, S-07)."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_tenant_db, get_tenant_id
from ..schemas.dashboard import DashboardMetrics, Incumplimientos
from ..services.dashboard import get_dashboard_metrics
from ..services.incumplimientos import listar as listar_incumplimientos

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
def dashboard_metrics(
    facility_id: UUID | None = Query(
        default=None,
        description="Acota las metricas a una planta. Si no pertenece al tenant, RLS devuelve vacio.",
    ),
    days_ahead: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Ventana de 'por vencer', en dias.",
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Todo lo que S-06 y S-07 necesitan, en una sola llamada.

    Un endpoint agregado y no cuatro sueltos: el Dashboard necesita conteos,
    no listas, y pedir `/obligations` entero para hacer `length` en el
    navegador no escala con datos reales.
    """
    return get_dashboard_metrics(db, tenant_id, facility_id, days_ahead)


@router.get(
    "/incumplimientos",
    response_model=Incumplimientos,
    tags=["business-logic"],
    summary="Que se esta incumpliendo, con su evidencia",
    description=(
        "El detalle detras del numero del tablero (#126). `/metrics` dice "
        "**cuanto**; esto dice **que**, y con que se respalda.\n\n"
        "Dos colecciones separadas porque son dos problemas distintos: un "
        "articulo evaluado como incumplido se resuelve con un plan de accion, y "
        "una declaracion vencida se resuelve presentandola. En una sola lista, "
        "la urgencia de una taparia la de la otra.\n\n"
        "**Los articulos vienen ordenados con los que NO tienen evidencia "
        "primero**, y el conteo va aparte en `articles_without_evidence`. Un "
        "incumplimiento documentado tiene algo que mostrar; uno sin evidencia "
        "deja a la empresa muda ante una fiscalizacion, y es el que hay que "
        "atender antes.\n\n"
        "Las listas tienen tope y **la respuesta dice si se corto** "
        "(`*_truncated`). Truncar en silencio se leeria como 'esto es todo lo "
        "que hay', que sobre incumplimientos es justo la lectura que no puede "
        "darse."
    ),
)
def incumplimientos(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Articulos incumplidos y declaraciones vencidas, con su evidencia."""
    return listar_incumplimientos(db, tenant_id)
