from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.organization import crud_tenant
from ..deps import get_db
from ..schemas.organization import TenantCreate, TenantRead, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/", response_model=list[TenantRead])
def list_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_tenant.get_multi(db, skip=skip, limit=limit)


@router.get("/{tenant_id}", response_model=TenantRead)
def get_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    obj = crud_tenant.get(db, tenant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return obj


@router.post("/", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(data: TenantCreate, db: Session = Depends(get_db)):
    obj = crud_tenant.create(db, obj_in=data)
    db.commit()
    return obj


@router.patch("/{tenant_id}", response_model=TenantRead)
def update_tenant(tenant_id: UUID, data: TenantUpdate, db: Session = Depends(get_db)):
    obj = crud_tenant.get(db, tenant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    obj = crud_tenant.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj
