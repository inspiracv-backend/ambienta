from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.iso14001 import crud_environmental_aspect, crud_regulated_equipment, crud_risk_opportunity
from ..deps import get_tenant_db, get_tenant_id
from ._comun import borrar_o_404, obtener_o_404
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


@router.delete("/aspects/{aspect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_aspect(aspect_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_environmental_aspect, db, aspect_id, recurso="EnvironmentalAspect")


@router.delete("/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk(risk_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_risk_opportunity, db, risk_id, recurso="RiskOpportunity")


@router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment(equipment_id: UUID, db: Session = Depends(get_tenant_db)):
    """Da de baja un equipo regulado. Sus operadores certificados quedan
    asociados: la certificacion de una persona es suya, no del equipo."""
    borrar_o_404(crud_regulated_equipment, db, equipment_id, recurso="RegulatedEquipment")


@router.get("/aspects/{aspect_id}", response_model=EnvironmentalAspectRead)
def get_aspect(aspect_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_environmental_aspect, db, aspect_id, recurso="EnvironmentalAspect")


@router.get("/risks/{risk_id}", response_model=RiskOpportunityRead)
def get_risk(risk_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_risk_opportunity, db, risk_id, recurso="RiskOpportunity")


@router.get("/equipment/{equipment_id}", response_model=RegulatedEquipmentRead)
def get_equipment(equipment_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_regulated_equipment, db, equipment_id, recurso="RegulatedEquipment")
