from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.obligations import crud_obligation, crud_task
from ..deps import get_tenant_db, get_tenant_id
from ..crud.compliance import crud_article_compliance, crud_matrix_norm
from ._comun import borrar_o_404, obtener_o_404, validar_visible
from ..schemas.obligations import (
    ObligationCreate,
    VincularAMatriz,
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
    # **Las claves foraneas no pasan por RLS.** Sin estas dos lineas, una
    # empresa podia colgar su obligacion de la evaluacion de otra: medido antes
    # de escribirlas, un id inventado daba 422 y uno real ajeno daba **201**.
    validar_visible(crud_article_compliance, db, data.article_compliance_id,
                    campo="article_compliance_id")
    validar_visible(crud_matrix_norm, db, data.matrix_norm_id, campo="matrix_norm_id")

    obj = crud_obligation.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{obligation_id}", response_model=ObligationRead)
def update_obligation(obligation_id: UUID, data: ObligationUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_obligation.get(db, obligation_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")
    validar_visible(crud_article_compliance, db, data.article_compliance_id,
                    campo="article_compliance_id")
    validar_visible(crud_matrix_norm, db, data.matrix_norm_id, campo="matrix_norm_id")

    obj = crud_obligation.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Vinculo con la Matriz Legal (RF-14) ──────────────────────────────────

@router.put(
    "/{obligation_id}/matrix-link",
    response_model=ObligationRead,
    tags=["business-logic"],
    summary="Vincular la obligacion a un articulo de la Matriz Legal",
    description=(
        "Ata una obligacion existente al articulo que la origina (RF-14): el "
        "sentido inverso a generarla desde la matriz.\n\n"
        "La norma y la planta se **reescriben** desde la evaluacion, para que "
        "las tres referencias no puedan contradecirse. Un articulo de otra "
        "empresa responde 422, igual que uno inexistente — distinguirlos "
        "permitiria enumerar identificadores ajenos."
    ),
)
def vincular_a_matriz(
    obligation_id: UUID,
    data: VincularAMatriz,
    db: Session = Depends(get_tenant_db),
):
    from ..services.vinculo_matriz_obligacion import EvaluacionInvisible, vincular

    obj = obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")
    try:
        obj = vincular(db, obligacion=obj, article_compliance_id=data.article_compliance_id)
    except EvaluacionInvisible as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    db.commit()
    return obj


@router.delete(
    "/{obligation_id}/matrix-link",
    response_model=ObligationRead,
    tags=["business-logic"],
    summary="Soltar la obligacion de la Matriz Legal",
    description=(
        "Quita el vinculo **sin borrar la obligacion**: sigue existiendo y "
        "venciendo. Lo que se pierde es la trazabilidad hacia el requisito que "
        "la origino, y por eso es una operacion propia y no un efecto colateral "
        "de editar un campo cualquiera.\n\n"
        "Responde 200 con la obligacion ya suelta, y no 204, porque el recurso "
        "sigue existiendo y quien llama necesita ver como quedo."
    ),
)
def desvincular_de_matriz(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    from ..services.vinculo_matriz_obligacion import desvincular

    obj = obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")
    obj = desvincular(db, obligacion=obj)
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


@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_obligation(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una obligacion. Sus tareas quedan igual: no se cascadea el
    borrado logico, porque tratarlas juntas impediria recuperarlas por
    separado si la baja fue un error."""
    borrar_o_404(crud_obligation, db, obligation_id, recurso="Obligation")


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_task, db, task_id, recurso="Task")


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_task, db, task_id, recurso="Task")
