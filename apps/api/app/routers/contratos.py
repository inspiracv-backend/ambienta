"""Contratos entre una consultora y su empresa cliente.

`ContractCreate` aceptaba `manager_tenant_id` y `client_tenant_id` del cuerpo,
validados solo por la clave foranea. Con eso una empresa podia crear un
contrato **declarandose gestora de otra**, o nombrando como cliente a alguien
que nunca lo acepto.

Lo que se corrige aca: `manager_tenant_id` lo fija el servidor con el tenant de
la sesion. Nadie puede decir que gestiona a nombre de otro.

**Lo que NO se resuelve**: el consentimiento de la contraparte. Nombrar a una
empresa como cliente sigue siendo unilateral. Hoy el dano esta acotado porque
`contracts` lleva `tenant_id` y RLS lo aplica: el contrato solo lo ve quien lo
creo, asi que es una afirmacion en sus propios registros, no un acceso a los
datos del otro. **Deja de estar acotado el dia que algo conceda permisos en
base a un contrato** — ahi hace falta el flujo de aceptacion.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..crud.organization import crud_contract
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.organization import ContractCreate, ContractRead, ContractUpdate
from ._paginacion import Pagina, paginacion, recortar
from ._comun import borrar_o_404, obtener_o_404

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/", response_model=list[ContractRead])
def list_contracts(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_contract.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.get("/{contract_id}", response_model=ContractRead)
def get_contract(contract_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_contract, db, contract_id, recurso="Contract")


@router.post("/", response_model=ContractRead, status_code=status.HTTP_201_CREATED)
def create_contract(
    data: ContractCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Registra un contrato.

    `manager_tenant_id` se ignora del cuerpo y se toma de la sesion: la gestora
    es quien registra el contrato, no quien lo diga el cliente.
    """
    datos = data.model_copy(update={"manager_tenant_id": tenant_id})
    obj = crud_contract.create(db, obj_in=datos, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{contract_id}", response_model=ContractRead)
def update_contract(contract_id: UUID, data: ContractUpdate, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_contract, db, contract_id, recurso="Contract")
    obj = crud_contract.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(contract_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira un contrato. Borrado logico: lo que se firmo se firmo, y el
    registro de que existio importa aunque la relacion termine."""
    borrar_o_404(crud_contract, db, contract_id, recurso="Contract")
