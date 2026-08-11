from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── Audit ─────────────────────────────────────────────────────────────────

class AuditCreate(BaseModel):
    facility_id: UUID | None = None
    code: str
    title: str
    audit_type: str
    scope: str
    lead_auditor_user_id: UUID | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    criteria: dict = Field(default_factory=dict)


class AuditRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    code: str
    title: str
    audit_type: str
    scope: str
    lead_auditor_user_id: UUID | None
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    status: str
    criteria: dict
    created_at: datetime
    updated_at: datetime


class AuditUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    criteria: dict | None = None


# ── AuditItem ─────────────────────────────────────────────────────────────

class AuditItemCreate(BaseModel):
    audit_id: UUID
    article_compliance_id: UUID | None = None
    sequence: int
    question: str
    auditor_user_id: UUID | None = None


class AuditItemRead(OrmBase):
    id: UUID
    tenant_id: UUID
    audit_id: UUID
    article_compliance_id: UUID | None
    sequence: int
    question: str
    result: str
    notes: str | None
    auditor_user_id: UUID | None
    assessed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuditItemUpdate(BaseModel):
    result: str | None = None
    notes: str | None = None
    assessed_at: datetime | None = None


# ── AuditParticipant ──────────────────────────────────────────────────────

class AuditParticipantCreate(BaseModel):
    audit_id: UUID
    user_id: UUID
    external_name: str | None = None
    external_email: str | None = None
    participant_role: str
    attendance_status: str = "invited"
    notes: str | None = None


class AuditParticipantRead(OrmBase):
    audit_id: UUID
    user_id: UUID
    tenant_id: UUID
    external_name: str | None
    external_email: str | None
    participant_role: str
    attendance_status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ── Nonconformity ─────────────────────────────────────────────────────────

class NonconformityCreate(BaseModel):
    facility_id: UUID | None = None
    audit_item_id: UUID | None = None
    article_compliance_id: UUID | None = None
    code: str
    title: str
    description: str
    severity: str
    record_type: str | None = None
    detection_origin: str | None = None
    owner_user_id: UUID | None = None
    due_date: date | None = None


class NonconformityRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    audit_item_id: UUID | None
    article_compliance_id: UUID | None
    code: str
    title: str
    description: str
    severity: str
    status: str
    record_type: str | None
    detection_origin: str | None
    root_cause_answers: list
    improvement_stages: dict
    detected_at: datetime
    detected_by: UUID | None
    owner_user_id: UUID | None
    due_date: date | None
    closed_at: datetime | None
    closure_notes: str | None
    created_at: datetime
    updated_at: datetime


class NonconformityUpdate(BaseModel):
    title: str | None = None
    severity: str | None = None
    status: str | None = None
    root_cause_answers: list | None = None
    improvement_stages: dict | None = None
    owner_user_id: UUID | None = None
    due_date: date | None = None
    closure_notes: str | None = None


# ── ActionPlan ────────────────────────────────────────────────────────────

class ActionPlanCreate(BaseModel):
    article_compliance_id: UUID | None = None
    nonconformity_id: UUID | None = None
    title: str
    root_cause: str | None = None
    objective: str
    priority: str = "medium"
    owner_user_id: UUID | None = None
    target_date: date | None = None
    success_criteria: dict = Field(default_factory=dict)


class ActionPlanRead(OrmBase):
    id: UUID
    tenant_id: UUID
    article_compliance_id: UUID | None
    nonconformity_id: UUID | None
    title: str
    root_cause: str | None
    objective: str
    status: str
    priority: str
    owner_user_id: UUID | None
    target_date: date | None
    verified_at: datetime | None
    verified_by: UUID | None
    success_criteria: dict
    created_at: datetime
    updated_at: datetime


class ActionPlanUpdate(BaseModel):
    title: str | None = None
    root_cause: str | None = None
    objective: str | None = None
    status: str | None = None
    priority: str | None = None
    owner_user_id: UUID | None = None
    target_date: date | None = None
    success_criteria: dict | None = None


# ── EntityStatusHistory ───────────────────────────────────────────────────

class EntityStatusHistoryRead(OrmBase):
    id: int
    tenant_id: UUID
    entity_type: str
    entity_id: UUID
    from_status: str | None
    to_status: str
    changed_at: datetime
    changed_by: UUID | None
    reason: str | None


class AuditParticipantUpdate(BaseModel):
    """Lo editable de un participante.

    `audit_id` y `user_id` no estan: son la clave compuesta, o sea la
    identidad de la fila. Cambiarlos no es editar, es otro participante.
    """

    participant_role: str | None = None
    attendance_status: str | None = None
    external_name: str | None = None
    external_email: str | None = None
    notes: str | None = None


class AuditParticipantCreateAnidado(BaseModel):
    """Cuerpo de `POST /audits/{audit_id}/participants/{user_id}`.

    La auditoria y la persona vienen del path: son la clave compuesta.
    """

    participant_role: str
    attendance_status: str = "invited"
    external_name: str | None = None
    external_email: str | None = None
    notes: str | None = None
