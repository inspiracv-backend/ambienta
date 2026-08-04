from pydantic import BaseModel

from ..models.system import AuditLog, IntegrationAccount
from ..schemas.system import AuditLogCreate, IntegrationAccountCreate
from .base import CRUDBase

crud_audit_log = CRUDBase[AuditLog, AuditLogCreate, BaseModel](AuditLog)
crud_integration_account = CRUDBase[IntegrationAccount, IntegrationAccountCreate, BaseModel](IntegrationAccount)
