from pydantic import BaseModel

from ..models.system import AuditLog, IntegrationAccount
from ..schemas.system import (
    AuditLogCreate,
    IntegrationAccountCreate,
    IntegrationAccountUpdate,
)
from .base import CRUDBase

crud_audit_log = CRUDBase[AuditLog, AuditLogCreate, BaseModel](AuditLog)
crud_integration_account = CRUDBase[
    IntegrationAccount, IntegrationAccountCreate, IntegrationAccountUpdate
](IntegrationAccount)
