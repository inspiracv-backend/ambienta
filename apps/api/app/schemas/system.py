from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── IntegrationAccount ────────────────────────────────────────────────────

class IntegrationAccountCreate(BaseModel):
    provider: str
    external_account_id: str | None = None
    display_name: str | None = None
    scopes: list[str] = Field(default_factory=list)
    secret_reference: str | None = None


class IntegrationAccountRead(OrmBase):
    id: UUID
    tenant_id: UUID
    provider: str
    external_account_id: str | None
    display_name: str | None
    status: str
    scopes: list[str]
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ── AuditLog ──────────────────────────────────────────────────────────────

class AuditLogCreate(BaseModel):
    actor_user_id: UUID | None = None
    action: str
    entity_type: str
    entity_id: UUID | None = None
    request_id: UUID | None = None
    ip_address: str | None = None
    reason: str | None = None
    before_data: dict | None = None
    after_data: dict | None = None
    metadata: dict = Field(default_factory=dict)


class AuditLogRead(OrmBase):
    id: int
    tenant_id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    request_id: UUID | None
    ip_address: str | None
    reason: str | None
    before_data: dict | None
    after_data: dict | None


class IntegrationAccountUpdate(BaseModel):
    """Lo editable de una cuenta de integracion.

    `provider` no esta: cambiar el proveedor de una cuenta existente no es una
    edicion, es otra cuenta — y dejaria `external_account_id`, `scopes` y el
    secreto apuntando a un sistema que ya no es el suyo.

    `secret_reference` si se puede cambiar, porque rotar credenciales es
    operacion normal. Nunca sale en la lectura: `IntegrationAccountRead` no lo
    incluye, y asi debe seguir.
    """

    external_account_id: str | None = None
    display_name: str | None = None
    status: str | None = None
    scopes: list[str] | None = None
    secret_reference: str | None = None
