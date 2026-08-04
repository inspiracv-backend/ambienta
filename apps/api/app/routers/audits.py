from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.audit import crud_action_plan, crud_audit, crud_audit_item, crud_nonconformity
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.audit import (
    ActionPlanCreate,
    ActionPlanRead,
    ActionPlanUpdate,
    AuditCreate,
    AuditItemCreate,
    AuditItemRead,
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
