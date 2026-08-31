"""Cuentas de integracion con sistemas externos.

Guarda con que proveedor esta conectada la empresa y con que alcance, no la
credencial: `secret_reference` es un puntero a donde vive el secreto de
verdad. Aun asi nunca se devuelve en las lecturas — un puntero tambien es
informacion util para quien no deberia tenerla.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..crud.system import crud_integration_account
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.system import (
    IntegrationAccountCreate,
    IntegrationAccountRead,
    IntegrationAccountUpdate,
)
from ._paginacion import Pagina, paginacion, recortar
from ._comun import borrar_o_404, obtener_o_404

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/", response_model=list[IntegrationAccountRead])
def list_integrations(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_integration_account.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.get("/{account_id}", response_model=IntegrationAccountRead)
def get_integration(account_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_integration_account, db, account_id, recurso="IntegrationAccount")


@router.post("/", response_model=IntegrationAccountRead, status_code=status.HTTP_201_CREATED)
def create_integration(
    data: IntegrationAccountCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_integration_account.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{account_id}", response_model=IntegrationAccountRead)
def update_integration(
    account_id: UUID, data: IntegrationAccountUpdate, db: Session = Depends(get_tenant_db)
):
    obj = obtener_o_404(crud_integration_account, db, account_id, recurso="IntegrationAccount")
    obj = crud_integration_account.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_integration(account_id: UUID, db: Session = Depends(get_tenant_db)):
    """Desconecta la integracion. El secreto en si lo revoca el proveedor: esto
    solo deja de usarlo."""
    borrar_o_404(crud_integration_account, db, account_id, recurso="IntegrationAccount")
