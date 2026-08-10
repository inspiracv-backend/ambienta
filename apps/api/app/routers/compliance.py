from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.compliance import crud_article_compliance, crud_matrix, crud_matrix_norm
from ..deps import get_tenant_db, get_tenant_id
from ._comun import borrar_o_404
from ..schemas.compliance import (
    ArticleComplianceCreate,
    ArticleComplianceRead,
    ArticleComplianceUpdate,
    MatrixNormCreate,
    MatrixNormRead,
    MatrixNormUpdate,
    TenantLegalMatrixCreate,
    TenantLegalMatrixRead,
    TenantLegalMatrixUpdate,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/matrices", response_model=list[TenantLegalMatrixRead])
def list_matrices(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_matrix.get_multi(db, skip=skip, limit=limit)


@router.get("/matrices/{matrix_id}", response_model=TenantLegalMatrixRead)
def get_matrix(matrix_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_matrix.get(db, matrix_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix not found")
    return obj


@router.post("/matrices", response_model=TenantLegalMatrixRead, status_code=status.HTTP_201_CREATED)
def create_matrix(
    data: TenantLegalMatrixCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_matrix.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/matrices/{matrix_id}", response_model=TenantLegalMatrixRead)
def update_matrix(matrix_id: UUID, data: TenantLegalMatrixUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_matrix.get(db, matrix_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix not found")
    obj = crud_matrix.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/matrix-norms", response_model=list[MatrixNormRead])
def list_matrix_norms(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_matrix_norm.get_multi(db, skip=skip, limit=limit)


@router.post("/matrix-norms", response_model=MatrixNormRead, status_code=status.HTTP_201_CREATED)
def create_matrix_norm(
    data: MatrixNormCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_matrix_norm.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/matrix-norms/{mn_id}", response_model=MatrixNormRead)
def update_matrix_norm(mn_id: UUID, data: MatrixNormUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_matrix_norm.get(db, mn_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix norm not found")
    obj = crud_matrix_norm.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/article-compliance", response_model=list[ArticleComplianceRead])
def list_article_compliance(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_article_compliance.get_multi(db, skip=skip, limit=limit)


@router.post("/article-compliance", response_model=ArticleComplianceRead, status_code=status.HTTP_201_CREATED)
def create_article_compliance(
    data: ArticleComplianceCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_article_compliance.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/article-compliance/{ac_id}", response_model=ArticleComplianceRead)
def update_article_compliance(ac_id: UUID, data: ArticleComplianceUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_article_compliance.get(db, ac_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article compliance not found")
    obj = crud_article_compliance.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Business Logic ──────────────────────────────────────────────────────

@router.get("/matrices/{matrix_id}/stats", tags=["business-logic"])
def matrix_stats(matrix_id: UUID, db: Session = Depends(get_tenant_db)):
    from ..services.compliance import get_compliance_stats
    try:
        return get_compliance_stats(db, matrix_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/article-compliance/{ac_id}/evaluate", response_model=ArticleComplianceRead, tags=["business-logic"])
def evaluate(
    ac_id: UUID,
    answer: str,
    compliance_method: str | None = None,
    evidence_url: str | None = None,
    db: Session = Depends(get_tenant_db),
):
    from ..services.compliance import evaluate_article
    try:
        obj = evaluate_article(db, ac_id, answer, compliance_method, evidence_url)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/matrices/{matrix_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_matrix(matrix_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una matriz legal de un periodo. Las evaluaciones por articulo
    quedan: son el historial de cumplimiento, no un detalle de la matriz."""
    borrar_o_404(crud_matrix, db, matrix_id, recurso="Matrix")


@router.delete("/matrix-norms/{mn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_matrix_norm(mn_id: UUID, db: Session = Depends(get_tenant_db)):
    """Saca una norma de la matriz: deja de aplicarle a la empresa."""
    borrar_o_404(crud_matrix_norm, db, mn_id, recurso="MatrixNorm")


@router.delete("/article-compliance/{ac_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article_compliance(ac_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_article_compliance, db, ac_id, recurso="ArticleCompliance")
