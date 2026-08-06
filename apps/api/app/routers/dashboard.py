"""Metricas agregadas del Dashboard (S-06, S-07)."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_tenant_db, get_tenant_id
from ..schemas.dashboard import DashboardMetrics
from ..services.dashboard import get_dashboard_metrics

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
