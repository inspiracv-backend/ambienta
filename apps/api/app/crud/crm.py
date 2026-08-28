from pydantic import BaseModel

from ..models.crm import CrmActivity, CrmCompany, CrmContact, CrmDeal, CrmStage
from ..schemas.crm import (
    CrmActivityCreate,
    CrmActivityUpdate,
    CrmCompanyCreate,
    CrmCompanyUpdate,
    CrmContactCreate,
    CrmContactUpdate,
    CrmDealUpdate,
    CrmStageCreate,
    CrmStageUpdate,
)
from .base import CRUDBase

crud_crm_stage = CRUDBase[CrmStage, CrmStageCreate, CrmStageUpdate](CrmStage)
crud_crm_company = CRUDBase[CrmCompany, CrmCompanyCreate, CrmCompanyUpdate](CrmCompany)
crud_crm_contact = CRUDBase[CrmContact, CrmContactCreate, CrmContactUpdate](CrmContact)
# `CrmDeal` se crea por el servicio —hay que resolver la etapa por defecto— asi
# que su `Create` no pasa por aca. El CRUD sirve para leer, actualizar y borrar.
crud_crm_deal = CRUDBase[CrmDeal, BaseModel, CrmDealUpdate](CrmDeal)
crud_crm_activity = CRUDBase[CrmActivity, CrmActivityCreate, CrmActivityUpdate](CrmActivity)
