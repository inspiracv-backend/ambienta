from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.organization import crud_user
from ..deps import get_tenant_db, get_tenant_id
from ._comun import borrar_o_404
from ..schemas.organization import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserRead])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_user.get_multi(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_user.get(db, user_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return obj


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_user.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: UUID, data: UserUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_user.get(db, user_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    obj = crud_user.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, db: Session = Depends(get_tenant_db)):
    """Saca a la persona de la empresa.

    Distinto de `status`: bloquear o deshabilitar es suspender —la persona
    sigue en la nomina y se puede revertir—, mientras que esto la retira. Su
    rastro en el registro de auditoria se conserva, que es lo que impide
    borrar la fila de verdad.
    """
    borrar_o_404(crud_user, db, user_id, recurso="User")
