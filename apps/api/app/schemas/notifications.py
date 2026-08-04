from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── NotificationTemplate ─────────────────────────────────────────────────

class NotificationTemplateCreate(BaseModel):
    code: str
    name: str
    event_type: str
    channel: str
    locale: str = "es-CL"
    subject_template: str | None = None
    body_template: str
    variables_schema: dict = Field(default_factory=dict)


class NotificationTemplateRead(OrmBase):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    event_type: str
    channel: str
    locale: str
    subject_template: str | None
    body_template: str
    variables_schema: dict
    version_no: int
    active: bool
    created_at: datetime
    updated_at: datetime


# ── NotificationRule ──────────────────────────────────────────────────────

class NotificationRuleCreate(BaseModel):
    event_type: str
    channel: str
    lead_minutes: int = 0
    recipient_rule: dict = Field(default_factory=dict)
    template_code: str


class NotificationRuleRead(OrmBase):
    id: UUID
    tenant_id: UUID
    event_type: str
    channel: str
    lead_minutes: int
    recipient_rule: dict
    template_code: str
    active: bool
    created_at: datetime
    updated_at: datetime


# ── Notification ──────────────────────────────────────────────────────────

class NotificationCreate(BaseModel):
    rule_id: UUID | None = None
    recipient_user_id: UUID | None = None
    channel: str
    subject: str | None = None
    body: str
    scheduled_at: datetime | None = None
    context: dict = Field(default_factory=dict)


class NotificationRead(OrmBase):
    id: UUID
    tenant_id: UUID
    rule_id: UUID | None
    recipient_user_id: UUID | None
    channel: str
    subject: str | None
    body: str
    status: str
    scheduled_at: datetime
    sent_at: datetime | None
    read_at: datetime | None
    provider_message_id: str | None
    context: dict
    created_at: datetime
    updated_at: datetime
