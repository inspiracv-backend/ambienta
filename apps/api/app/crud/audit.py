from ..models.audit import (
    ActionPlan,
    Audit,
    AuditItem,
    ImprovementMethodology,
    ImprovementSeverity,
    Nonconformity,
)
from ..schemas.audit import (
    ActionPlanCreate,
    ActionPlanUpdate,
    AuditCreate,
    AuditItemCreate,
    AuditItemUpdate,
    AuditUpdate,
    MetodologiaCreate,
    MetodologiaUpdate,
    NonconformityCreate,
    NonconformityUpdate,
    SeveridadCreate,
    SeveridadUpdate,
)
from .base import CRUDBase

crud_audit = CRUDBase[Audit, AuditCreate, AuditUpdate](Audit)
crud_audit_item = CRUDBase[AuditItem, AuditItemCreate, AuditItemUpdate](AuditItem)
crud_nonconformity = CRUDBase[Nonconformity, NonconformityCreate, NonconformityUpdate](Nonconformity)
crud_action_plan = CRUDBase[ActionPlan, ActionPlanCreate, ActionPlanUpdate](ActionPlan)


# Los catalogos configurables por empresa (RF-100, #41).
crud_severidad = CRUDBase[ImprovementSeverity, SeveridadCreate, SeveridadUpdate](
    ImprovementSeverity
)
crud_metodologia = CRUDBase[
    ImprovementMethodology, MetodologiaCreate, MetodologiaUpdate
](ImprovementMethodology)
