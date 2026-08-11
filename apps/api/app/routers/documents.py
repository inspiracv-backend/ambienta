from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.documents import crud_document, crud_entity_document
from ..deps import get_tenant_db, get_tenant_id
from ..models.documents import EntityDocument
from ._comun import borrar_o_404, listar_por_padre, obtener_o_404, verificar_padre
from ..schemas.documents import (
    DocumentCreate,
    EntityDocumentCreate,
    EntityDocumentCreateAnidado,
    EntityDocumentRead,
    EntityDocumentUpdate,
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


# ── Vinculos del documento con las entidades que respalda ──────────────────

@router.get("/{document_id}/entities", response_model=list[EntityDocumentRead])
def list_entity_documents(document_id: UUID, db: Session = Depends(get_tenant_db)):
    """A que entidades respalda este documento."""
    obtener_o_404(crud_document, db, document_id, recurso="Document")
    return listar_por_padre(EntityDocument, db, document_id, campo="document_id")


@router.post("/{document_id}/entities", response_model=EntityDocumentRead, status_code=status.HTTP_201_CREATED)
def create_entity_document(
    document_id: UUID,
    data: EntityDocumentCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Vincula el documento con la entidad que respalda.

    `document_id` sale del path y se ignora del cuerpo: si viniera del cuerpo,
    la URL podria decir un documento y la fila apuntar a otro.
    """
    obtener_o_404(crud_document, db, document_id, recurso="Document")
    datos = data.model_dump()
    datos["document_id"] = document_id
    obj = crud_entity_document.create(
        db, obj_in=EntityDocumentCreate(**datos), tenant_id=tenant_id
    )
    db.commit()
    return obj


@router.patch("/{document_id}/entities/{vinculo_id}", response_model=EntityDocumentRead)
def update_entity_document(
    document_id: UUID, vinculo_id: int, data: EntityDocumentUpdate, db: Session = Depends(get_tenant_db)
):
    obj = obtener_o_404(crud_entity_document, db, vinculo_id, recurso="EntityDocument")
    verificar_padre(obj, document_id, campo="document_id")
    obj = crud_entity_document.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{document_id}/entities/{vinculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity_document(document_id: UUID, vinculo_id: int, db: Session = Depends(get_tenant_db)):
    """Desvincula el documento de esa entidad. El documento no se toca."""
    obj = obtener_o_404(crud_entity_document, db, vinculo_id, recurso="EntityDocument")
    verificar_padre(obj, document_id, campo="document_id")
    borrar_o_404(crud_entity_document, db, vinculo_id, recurso="EntityDocument")


@router.get("/{document_id}/entities/{vinculo_id}", response_model=EntityDocumentRead)
def get_entity_document(document_id: UUID, vinculo_id: int, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_entity_document, db, vinculo_id, recurso="EntityDocument")
    return verificar_padre(obj, document_id, campo="document_id")
