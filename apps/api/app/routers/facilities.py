from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.organization import crud_facility
from ..deps import get_tenant_db, get_tenant_id
from ._comun import borrar_o_404
from ..schemas.organization import FacilityCreate, FacilityRead, FacilityUpdate

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("/", response_model=list[FacilityRead])
def list_facilities(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_tenant_db),
):
    return crud_facility.get_multi(db, skip=skip, limit=limit)


@router.get("/{facility_id}", response_model=FacilityRead)
def get_facility(facility_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_facility.get(db, facility_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    return obj


@router.post("/", response_model=FacilityRead, status_code=status.HTTP_201_CREATED)
def create_facility(
    data: FacilityCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_facility.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{facility_id}", response_model=FacilityRead)
def update_facility(
    facility_id: UUID,
    data: FacilityUpdate,
    db: Session = Depends(get_tenant_db),
):
    obj = crud_facility.get(db, facility_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    obj = crud_facility.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(facility_id: UUID, db: Session = Depends(get_tenant_db)):
    """Da de baja una instalacion. Borrado logico: sus obligaciones y
    evaluaciones siguen referenciandola en el historial."""
    borrar_o_404(crud_facility, db, facility_id, recurso="Facility")
