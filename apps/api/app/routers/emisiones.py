"""Quien emitio que documento (RNF-26, decision 9 del 21-sep).

Lo que sale del sistema hacia una auditoria externa —un informe de auditoria,
la matriz de aspectos, un reporte— es lo que RNF-26 pide poder rastrear. Hasta
el 21-sep se anotaba en el historial **de la sesion del navegador**, que se
vacia al recargar: el servidor no sabia que alguien se habia llevado una copia.

Spec: `openspec/changes/registro-de-actividades` (y despues del archivo,
`openspec/specs/registro-de-actividades`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..crud.audit import crud_audit
from ..deps import get_current_user, get_tenant_db, get_tenant_id
from ..models.organization import User
from ..services.auditoria import registrar
from ._comun import validar_visible

router = APIRouter(prefix="/emisiones", tags=["system"])

#: Los documentos que se pueden anotar. **Lista cerrada**: un valor libre haria
#: imposible filtrar el registro por lo que se emitio.
DOCUMENTOS = ("informe_de_auditoria", "matriz_de_aspectos", "reporte")


class EmisionCreate(BaseModel):
    documento: Literal["informe_de_auditoria", "matriz_de_aspectos", "reporte"]
    titulo: str = Field(min_length=1, max_length=300)
    formato: Literal["pdf", "csv"]
    #: Cuantas filas llevaba. Una matriz filtrada sin aviso se lee como entera.
    filas: int | None = Field(default=None, ge=0)
    filtros: list[str] = Field(default_factory=list, max_length=20)
    #: El registro al que pertenece el documento, si hay uno. Hoy solo el
    #: informe de auditoria: asi la emision aparece en el historial de su ficha.
    entidad_tipo: Literal["audits"] | None = None
    entidad_id: UUID | None = None

    @model_validator(mode="after")
    def _entidad_completa(self) -> "EmisionCreate":
        if (self.entidad_tipo is None) != (self.entidad_id is None):
            raise ValueError("entidad_tipo y entidad_id van juntos, o ninguno de los dos")
        return self


class EmisionRead(BaseModel):
    id: int
    occurred_at: datetime
    action: str
    entity_type: str
    entity_id: UUID | None


@router.post(
    "/",
    response_model=EmisionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Anotar que se emitio un documento",
    description=(
        "Deja en el registro de actividades que alguien emitio un informe, una "
        "matriz o un reporte, con que filtros y cuantas filas (RNF-26). Accion "
        "`download`.\n\n"
        "Se anota **al abrir la impresion**: el navegador no avisa si se cancela. "
        "Una empresa suspendida puede exportar, y su emision queda anotada igual."
    ),
)
def anotar_emision(
    datos: EmisionCreate,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    # **Si nombra un registro, tiene que ser de esta empresa**: las claves que
    # llegan del cuerpo no pasan por RLS, y anotar contra una auditoria ajena
    # seria un oraculo para saber que ids existen.
    if datos.entidad_tipo == "audits" and datos.entidad_id is not None:
        validar_visible(crud_audit, db, datos.entidad_id, campo="entidad_id")

    actor = (
        db.scalar(select(User.id).where(User.clerk_id == user.user_id)) if user.user_id else None
    )
    entrada = registrar(
        db,
        tenant_id=tenant_id,
        action="download",
        entity_type=datos.entidad_tipo or "tenants",
        entity_id=datos.entidad_id or tenant_id,
        actor_user_id=actor,
        despues={
            "documento": datos.documento,
            "titulo": datos.titulo,
            "formato": datos.formato,
            "filas": datos.filas,
            "filtros": datos.filtros,
        },
        metadata={
            "ruta": f"{request.method} {request.url.path}",
            "nota": "se abrio la impresion o se descargo; el navegador no avisa si se cancela",
        },
    )
    # Se lee antes de confirmar: despues del commit la sesion no tiene empresa.
    db.flush()
    db.refresh(entrada)
    leida = EmisionRead(
        id=entrada.id,
        occurred_at=entrada.occurred_at,
        action=entrada.action,
        entity_type=entrada.entity_type,
        entity_id=entrada.entity_id,
    )
    db.commit()
    return leida
