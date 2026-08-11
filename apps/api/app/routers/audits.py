from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.audit import (
    crud_action_plan,
    crud_audit,
    crud_audit_item,
    crud_nonconformity,
)
from ..deps import get_tenant_db, get_tenant_id
from ..crud.organization import crud_user
from ..models.audit import AuditItem, AuditParticipant
from ._comun import (
    CRUDAsociacion,
    borrar_o_404,
    listar_por_padre,
    obtener_o_404,
    validar_visible,
    verificar_padre,
)
from ..schemas.audit import (
    AuditItemUpdate,
    AuditItemRead,
    AuditItemCreate,
    AuditItemCreateAnidado,
    ActionPlanCreate,
    AuditParticipantCreateAnidado,
    AuditParticipantRead,
    AuditParticipantUpdate,
    ActionPlanRead,
    ActionPlanUpdate,
    AuditCreate,
    AuditRead,
    AuditUpdate,
    NonconformityCreate,
    NonconformityRead,
    NonconformityUpdate,
)

router = APIRouter(prefix="/audits", tags=["audits"])


@router.get("/", response_model=list[AuditRead])
def list_audits(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_audit.get_multi(db, skip=skip, limit=limit)


@router.get("/{audit_id}", response_model=AuditRead)
def get_audit(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_audit.get(db, audit_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    return obj


@router.post("/", response_model=AuditRead, status_code=status.HTTP_201_CREATED)
def create_audit(
    data: AuditCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_audit.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{audit_id}", response_model=AuditRead)
def update_audit(audit_id: UUID, data: AuditUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_audit.get(db, audit_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    obj = crud_audit.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Nonconformities ──────────────────────────────────────────────────────

@router.get("/nonconformities/", response_model=list[NonconformityRead], tags=["nonconformities"])
def list_nonconformities(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_nonconformity.get_multi(db, skip=skip, limit=limit)


@router.post("/nonconformities/", response_model=NonconformityRead, status_code=status.HTTP_201_CREATED, tags=["nonconformities"])
def create_nonconformity(
    data: NonconformityCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_nonconformity.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/nonconformities/{nc_id}", response_model=NonconformityRead, tags=["nonconformities"])
def update_nonconformity(nc_id: UUID, data: NonconformityUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_nonconformity.get(db, nc_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nonconformity not found")
    obj = crud_nonconformity.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Action Plans ─────────────────────────────────────────────────────────

@router.get("/action-plans/", response_model=list[ActionPlanRead], tags=["action-plans"])
def list_action_plans(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_action_plan.get_multi(db, skip=skip, limit=limit)


@router.post("/action-plans/", response_model=ActionPlanRead, status_code=status.HTTP_201_CREATED, tags=["action-plans"])
def create_action_plan(
    data: ActionPlanCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_action_plan.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/action-plans/{plan_id}", response_model=ActionPlanRead, tags=["action-plans"])
def update_action_plan(plan_id: UUID, data: ActionPlanUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_action_plan.get(db, plan_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
    obj = crud_action_plan.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Business Logic ──────────────────────────────────────────────────────

@router.post("/{audit_id}/advance", response_model=AuditRead, tags=["business-logic"])
def advance_status(audit_id: UUID, new_status: str, db: Session = Depends(get_tenant_db)):
    from ..services.audits import advance_audit_status
    try:
        obj = advance_audit_status(db, audit_id, new_status)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{audit_id}/summary", tags=["business-logic"])
def audit_summary(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    from ..services.audits import get_audit_summary
    try:
        return get_audit_summary(db, audit_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/nonconformities/{nc_id}/close", response_model=NonconformityRead, tags=["business-logic"])
def close_nc(nc_id: UUID, closure_notes: str = "", db: Session = Depends(get_tenant_db)):
    from ..services.audits import close_nonconformity
    try:
        obj = close_nonconformity(db, nc_id, closure_notes)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/action-plans/{plan_id}/verify", response_model=ActionPlanRead, tags=["business-logic"])
def verify_plan(
    plan_id: UUID,
    success: bool = True,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..services.audits import verify_action_plan
    try:
        obj = verify_action_plan(db, plan_id, tenant_id, success)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{audit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_audit(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una auditoria. Sus hallazgos y no conformidades no se tocan:
    una no conformidad sobrevive a la auditoria que la origino."""
    borrar_o_404(crud_audit, db, audit_id, recurso="Audit")


@router.delete("/nonconformities/{nc_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["nonconformities"])
def delete_nonconformity(nc_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una no conformidad registrada por error.

    Cerrarla es otra cosa y va por `/nonconformities/{id}/close`: cerrar
    significa que se resolvio, esto que no debio existir.
    """
    borrar_o_404(crud_nonconformity, db, nc_id, recurso="Nonconformity")


@router.delete("/action-plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["action-plans"])
def delete_action_plan(plan_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_action_plan, db, plan_id, recurso="ActionPlan")


@router.get("/nonconformities/{nc_id}", response_model=NonconformityRead, tags=["nonconformities"])
def get_nonconformity(nc_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_nonconformity, db, nc_id, recurso="Nonconformity")


@router.get("/action-plans/{plan_id}", response_model=ActionPlanRead, tags=["action-plans"])
def get_action_plan(plan_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_action_plan, db, plan_id, recurso="ActionPlan")


# ── Participantes de una auditoria (clave compuesta, anidada) ──────────────

crud_participante = CRUDAsociacion(AuditParticipant, "audit_id", "user_id")


@router.get("/{audit_id}/participants", response_model=list[AuditParticipantRead], tags=["audits"])
def list_participants(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    return crud_participante.listar(db, audit_id)


@router.post("/{audit_id}/participants/{user_id}", response_model=AuditParticipantRead, status_code=status.HTTP_201_CREATED, tags=["audits"])
def add_participant(
    audit_id: UUID,
    user_id: UUID,
    data: AuditParticipantCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Suma a alguien a la auditoria.

    El usuario va en el path y no en el cuerpo para que la URL identifique por
    completo la fila: la clave es (audit_id, user_id).
    """
    obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    validar_visible(crud_user, db, user_id, campo="user_id")
    if crud_participante.obtener(db, audit_id, user_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esa persona ya participa en la auditoria.",
        )
    obj = crud_participante.crear(db, padre_id=audit_id, hijo_id=user_id, datos=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{audit_id}/participants/{user_id}", response_model=AuditParticipantRead, tags=["audits"])
def update_participant(
    audit_id: UUID, user_id: UUID, data: AuditParticipantUpdate, db: Session = Depends(get_tenant_db)
):
    obj = crud_participante.obtener(db, audit_id, user_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    obj = crud_participante.actualizar(db, db_obj=obj, datos=data)
    db.commit()
    return obj


@router.delete("/{audit_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["audits"])
def remove_participant(audit_id: UUID, user_id: UUID, db: Session = Depends(get_tenant_db)):
    """Saca a alguien de la auditoria. Borrado logico: quien participo es
    parte del registro de esa auditoria, aunque despues se le retire."""
    if crud_participante.borrar(db, padre_id=audit_id, hijo_id=user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    db.commit()


@router.get("/{audit_id}/participants/{user_id}", response_model=AuditParticipantRead, tags=["audits"])
def get_participant(audit_id: UUID, user_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_participante.obtener(db, audit_id, user_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return obj


# ── Hallazgos de una auditoria ─────────────────────────────────────────────

@router.get("/{audit_id}/items", response_model=list[AuditItemRead], tags=["audits"])
def list_audit_items(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    return listar_por_padre(AuditItem, db, audit_id, campo="audit_id")


@router.post("/{audit_id}/items", response_model=AuditItemRead, status_code=status.HTTP_201_CREATED, tags=["audits"])
def create_audit_item(
    audit_id: UUID,
    data: AuditItemCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    datos = data.model_dump()
    datos["audit_id"] = audit_id
    obj = crud_audit_item.create(db, obj_in=AuditItemCreate(**datos), tenant_id=tenant_id)
    db.commit()
    return obj


@router.get("/{audit_id}/items/{item_id}", response_model=AuditItemRead, tags=["audits"])
def get_audit_item(audit_id: UUID, item_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_audit_item, db, item_id, recurso="AuditItem")
    return verificar_padre(obj, audit_id, campo="audit_id")


@router.patch("/{audit_id}/items/{item_id}", response_model=AuditItemRead, tags=["audits"])
def update_audit_item(audit_id: UUID, item_id: UUID, data: AuditItemUpdate, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_audit_item, db, item_id, recurso="AuditItem")
    verificar_padre(obj, audit_id, campo="audit_id")
    obj = crud_audit_item.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{audit_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["audits"])
def delete_audit_item(audit_id: UUID, item_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira un hallazgo registrado por error. Las no conformidades que haya
    originado no se tocan: viven mas alla del hallazgo."""
    obj = obtener_o_404(crud_audit_item, db, item_id, recurso="AuditItem")
    verificar_padre(obj, audit_id, campo="audit_id")
    borrar_o_404(crud_audit_item, db, item_id, recurso="AuditItem")
