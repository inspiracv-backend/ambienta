"""La historia de un registro (RF-113, #75).

Un router y no uno por entidad, por el mismo motivo que los comentarios: el
`entity_type` dice de que registro se pide la historia, y trece copias de la
misma consulta serian trece lugares donde olvidar la comprobacion del anclaje.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..deps import get_current_user, get_tenant_db
from ..models.organization import User
from ..services import historial as svc
from ..services.permisos import tiene_permiso
from ..services.vinculos_de_documentos import familia_de

router = APIRouter(prefix="/historial", tags=["historial"])


class EventoRead(BaseModel):
    tipo: str
    ocurrido_el: datetime
    actor_id: UUID | None
    actor: str | None
    resumen: str
    detalle: dict[str, Any]


class HistoriaRead(BaseModel):
    eventos: list[EventoRead]
    #: Que origenes componen esta historia.
    fuentes: list[str]
    #: **Los que RF-113 nombra y todavia no existen.** Hoy: el correo (RF-107,
    #: #72). Se declara para que la pantalla lo diga: una linea de tiempo sin
    #: correos que no avisa hace concluir que no hubo correos.
    fuentes_pendientes: list[str]
    #: `True` si se alcanzo el tope y hay historia anterior sin devolver. Una
    #: lista cortada en silencio afirma que eso es todo lo que paso.
    hay_mas: bool


@router.get("/", response_model=HistoriaRead, summary="Historia de un registro")
def leer_historia(
    entity_type: str = Query(...),
    entity_id: UUID = Query(...),
    actual: CurrentUser | None = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """Actividad, conversacion y adjuntos de un registro, en una sola linea.

    Exige `<familia>.read` cuando hay sesion identificada: una linea de tiempo
    es una lectura del registro, asi que no puede pedir menos que leerlo. Sin
    sesion —el modo `X-Tenant-Id` de desarrollo— no hay de donde sacar
    permisos y RLS ya acota las filas.
    """
    if actual is not None and actual.user_id:
        quien = db.scalars(
            select(User).where(
                User.clerk_id == actual.user_id, User.deleted_at.is_(None)
            )
        ).first()
        if quien is not None:
            codigo = f"{familia_de(entity_type)}.read"
            if not tiene_permiso(db, quien.id, codigo):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Falta el permiso {codigo}.",
                )

    historia = svc.construir(db, entity_type, entity_id)
    return HistoriaRead(
        eventos=[EventoRead(**vars(e)) for e in historia.eventos],
        fuentes=list(historia.fuentes),
        fuentes_pendientes=list(historia.fuentes_pendientes),
        hay_mas=historia.hay_mas,
    )
