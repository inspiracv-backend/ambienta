from pydantic import BaseModel

from ..models.iso14001 import EnvironmentalAspect, EquipmentOperator, RegulatedEquipment, RiskOpportunity
from ..schemas.iso14001 import (
    EnvironmentalAspectCreate,
    EnvironmentalAspectUpdate,
    EquipmentOperatorCreate,
    RegulatedEquipmentCreate,
    RegulatedEquipmentUpdate,
    RiskOpportunityCreate,
    RiskOpportunityUpdate,
)
from .base import CRUDBase

crud_environmental_aspect = CRUDBase[EnvironmentalAspect, EnvironmentalAspectCreate, EnvironmentalAspectUpdate](EnvironmentalAspect)
crud_risk_opportunity = CRUDBase[RiskOpportunity, RiskOpportunityCreate, RiskOpportunityUpdate](RiskOpportunity)
crud_regulated_equipment = CRUDBase[RegulatedEquipment, RegulatedEquipmentCreate, RegulatedEquipmentUpdate](RegulatedEquipment)
crud_equipment_operator = CRUDBase[EquipmentOperator, EquipmentOperatorCreate, BaseModel](EquipmentOperator)
