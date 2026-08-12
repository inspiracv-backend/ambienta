from ..models.audit import ActionPlan, Audit, AuditItem, Nonconformity
from ..schemas.audit import (
    ActionPlanCreate,
    ActionPlanUpdate,
    AuditCreate,
    AuditItemCreate,
    AuditItemUpdate,
    AuditUpdate,
    NonconformityCreate,
    NonconformityUpdate,
)
from .base import CRUDBase

crud_audit = CRUDBase[Audit, AuditCreate, AuditUpdate](Audit)
crud_audit_item = CRUDBase[AuditItem, AuditItemCreate, AuditItemUpdate](AuditItem)
crud_nonconformity = CRUDBase[Nonconformity, NonconformityCreate, NonconformityUpdate](Nonconformity)
crud_action_plan = CRUDBase[ActionPlan, ActionPlanCreate, ActionPlanUpdate](ActionPlan)
