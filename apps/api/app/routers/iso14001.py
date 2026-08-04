from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.iso14001 import crud_environmental_aspect, crud_regulated_equipment, crud_risk_opportunity
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.iso14001 import (
    EnvironmentalAspectCreate,
    EnvironmentalAspectRead,
    EnvironmentalAspectUpdate,
    RegulatedEquipmentCreate,
    RegulatedEquipmentRead,
    RegulatedEquipmentUpdate,
    RiskOpportunityCreate,
    RiskOpportunityRead,
    RiskOpportunityUpdate,
)

router = APIRouter(prefix="/iso14001", tags=["iso14001"])


@router.get("/aspects", response_model=list[EnvironmentalAspectRead])
def list_aspects(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_environmental_aspect.get_multi(db, skip=skip, limit=limit)


@router.post("/aspects", response_model=EnvironmentalAspectRead, status_code=status.HTTP_201_CREATED)
def create_aspect(
    data: EnvironmentalAspectCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_environmental_aspect.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/aspects/{aspect_id}", response_model=EnvironmentalAspectRead)
def update_aspect(aspect_id: UUID, data: EnvironmentalAspectUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_environmental_aspect.get(db, aspect_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aspect not found")
    obj = crud_environmental_aspect.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/risks", response_model=list[RiskOpportunityRead])
def list_risks(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_risk_opportunity.get_multi(db, skip=skip, limit=limit)


@router.post("/risks", response_model=RiskOpportunityRead, status_code=status.HTTP_201_CREATED)
def create_risk(
    data: RiskOpportunityCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_risk_opportunity.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/risks/{risk_id}", response_model=RiskOpportunityRead)
def update_risk(risk_id: UUID, data: RiskOpportunityUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_risk_opportunity.get(db, risk_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    obj = crud_risk_opportunity.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/equipment", response_model=list[RegulatedEquipmentRead])
def list_equipment(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_regulated_equipment.get_multi(db, skip=skip, limit=limit)


@router.post("/equipment", response_model=RegulatedEquipmentRead, status_code=status.HTTP_201_CREATED)
def create_equipment(
    data: RegulatedEquipmentCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_regulated_equipment.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/equipment/{equipment_id}", response_model=RegulatedEquipmentRead)
def update_equipment(equipment_id: UUID, data: RegulatedEquipmentUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_regulated_equipment.get(db, equipment_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    obj = crud_regulated_equipment.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj
