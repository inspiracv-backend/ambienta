from ..models.audit import (
    ActionPlan,
    Audit,
    AuditItem,
    AuditProcessResult,
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
    VeredictoDeProcesoCreate,
    VeredictoDeProcesoUpdate,
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

# El veredicto del auditor sobre cada proceso (RF-101, #42).
crud_veredicto_de_proceso = CRUDBase[
    AuditProcessResult, VeredictoDeProcesoCreate, VeredictoDeProcesoUpdate
](AuditProcessResult)
