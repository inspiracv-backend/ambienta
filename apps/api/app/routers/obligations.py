from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.obligations import crud_obligation, crud_task
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.obligations import (
    ObligationCreate,
    ObligationRead,
    ObligationUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)

router = APIRouter(prefix="/obligations", tags=["obligations"])


@router.get("/", response_model=list[ObligationRead])
def list_obligations(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_obligation.get_multi(db, skip=skip, limit=limit)


@router.get("/{obligation_id}", response_model=ObligationRead)
def get_obligation(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_obligation.get(db, obligation_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")
    return obj


@router.post("/", response_model=ObligationRead, status_code=status.HTTP_201_CREATED)
def create_obligation(
    data: ObligationCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_obligation.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{obligation_id}", response_model=ObligationRead)
def update_obligation(obligation_id: UUID, data: ObligationUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_obligation.get(db, obligation_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")
    obj = crud_obligation.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Tasks ────────────────────────────────────────────────────────────────

@router.get("/{obligation_id}/tasks", response_model=list[TaskRead])
def list_tasks(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    from sqlalchemy import select
    from ..models.obligations import Task
    stmt = select(Task).where(Task.obligation_id == obligation_id)
    return list(db.scalars(stmt).all())


@router.post("/{obligation_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    obligation_id: UUID,
    data: TaskCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    task_data = data.model_dump(exclude_unset=True)
    task_data["obligation_id"] = obligation_id
    from ..models.obligations import Task
    obj = Task(**task_data, tenant_id=tenant_id)
    db.add(obj)
    db.flush()
    db.refresh(obj)
    db.commit()
    return obj


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: UUID, data: TaskUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_task.get(db, task_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    obj = crud_task.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Business Logic ──────────────────────────────────────────────────────

@router.get("/upcoming/", response_model=list[ObligationRead], tags=["business-logic"])
def list_upcoming(
    days: int = 30,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..services.obligations import get_upcoming_obligations
    return get_upcoming_obligations(db, tenant_id, days)


@router.get("/overdue/", response_model=list[ObligationRead], tags=["business-logic"])
def list_overdue(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..services.obligations import get_overdue_obligations
    return get_overdue_obligations(db, tenant_id)


@router.post("/{obligation_id}/submit", response_model=ObligationRead, tags=["business-logic"])
def submit(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    from ..services.obligations import submit_obligation
    try:
        obj = submit_obligation(db, obligation_id, obligation_id)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{obligation_id}/fulfill", response_model=ObligationRead, tags=["business-logic"])
def fulfill(obligation_id: UUID, receipt: str | None = None, db: Session = Depends(get_tenant_db)):
    from ..services.obligations import fulfill_obligation
    try:
        obj = fulfill_obligation(db, obligation_id, receipt)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/generate-notifications/", tags=["business-logic"])
def generate_notifications(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..services.obligations import create_deadline_notifications
    notifications = create_deadline_notifications(db, tenant_id)
    db.commit()
    return {"created": len(notifications)}
