"""Declaraciones enviadas a la autoridad.

Es lo que cierra una obligacion: la obligacion dice "hay que declarar el
SIDREP del primer semestre", y la declaracion es el envio concreto con su
folio y su comprobante.

Ruta propia y no anidada bajo `/obligations` porque una declaracion tambien se
consulta por si sola —"que enviamos este semestre"— y porque `obligation_id`
puede quedar nulo en envios que no responden a una obligacion registrada.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..crud.obligations import crud_declaration_submission
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.obligations import (
    DeclarationSubmissionCreate,
    DeclarationSubmissionRead,
    DeclarationSubmissionUpdate,
)
from ._comun import borrar_o_404, obtener_o_404

router = APIRouter(prefix="/declarations", tags=["declarations"])


@router.get("/", response_model=list[DeclarationSubmissionRead])
def list_declarations(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_declaration_submission.get_multi(db, skip=skip, limit=limit)


@router.get("/{declaration_id}", response_model=DeclarationSubmissionRead)
def get_declaration(declaration_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_declaration_submission, db, declaration_id, recurso="DeclarationSubmission")


@router.post("/", response_model=DeclarationSubmissionRead, status_code=status.HTTP_201_CREATED)
def create_declaration(
    data: DeclarationSubmissionCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_declaration_submission.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{declaration_id}", response_model=DeclarationSubmissionRead)
def update_declaration(declaration_id: UUID, data: DeclarationSubmissionUpdate, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_declaration_submission, db, declaration_id, recurso="DeclarationSubmission")
    obj = crud_declaration_submission.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{declaration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_declaration(declaration_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una declaracion cargada por error.

    Borrado logico: lo que se envio a la autoridad se envio, y el registro de
    que existio importa aunque la fila se retire de la vista.
    """
    borrar_o_404(crud_declaration_submission, db, declaration_id, recurso="DeclarationSubmission")
