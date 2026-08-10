from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.documents import crud_document
from ..deps import get_tenant_db, get_tenant_id
from ._comun import borrar_o_404
from ..schemas.documents import (
    DocumentCreate,
    DocumentRead,
    DocumentUpdate,
    DocumentVersionCreate,
    DocumentVersionRead,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentRead])
def list_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_document.get_multi(db, skip=skip, limit=limit)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_document.get(db, document_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return obj


@router.post("/", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(
    data: DocumentCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_document.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document(document_id: UUID, data: DocumentUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_document.get(db, document_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    obj = crud_document.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/{document_id}/versions", response_model=list[DocumentVersionRead])
def list_versions(document_id: UUID, db: Session = Depends(get_tenant_db)):
    from sqlalchemy import select
    from ..models.documents import DocumentVersion
    stmt = select(DocumentVersion).where(DocumentVersion.document_id == document_id)
    return list(db.scalars(stmt).all())


@router.post("/{document_id}/versions", response_model=DocumentVersionRead, status_code=status.HTTP_201_CREATED)
def create_version(
    document_id: UUID,
    data: DocumentVersionCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..models.documents import DocumentVersion
    version_data = data.model_dump(exclude_unset=True)
    version_data["document_id"] = document_id
    obj = DocumentVersion(**version_data, tenant_id=tenant_id)
    db.add(obj)
    db.flush()
    db.refresh(obj)
    db.commit()
    return obj


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira un documento. Sus versiones no se exponen para borrado: son la
    evidencia que respalda el cumplimiento, y eliminarlas dejaria sin sustento
    a las evaluaciones que las citan."""
    borrar_o_404(crud_document, db, document_id, recurso="Document")
