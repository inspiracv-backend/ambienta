from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── ObligationTemplate ────────────────────────────────────────────────────

class ObligationTemplateRead(OrmBase):
    id: UUID
    country_id: int
    code: str
    name: str
    authority: str | None
    frequency_rule: str | None
    default_lead_days: int
    template_config: dict
    active: bool
    created_at: datetime
    updated_at: datetime


# ── Obligation ────────────────────────────────────────────────────────────

class ObligationCreate(BaseModel):
    template_id: UUID | None = None
    matrix_norm_id: UUID | None = None
    article_compliance_id: UUID | None = None
    facility_id: UUID | None = None
    code: str
    title: str
    period_start: date | None = None
    period_end: date | None = None
    due_at: datetime | None = None
    owner_user_id: UUID | None = None
    data: dict = Field(default_factory=dict)


class ObligationRead(OrmBase):
    id: UUID
    tenant_id: UUID
    template_id: UUID | None
    matrix_norm_id: UUID | None
    article_compliance_id: UUID | None
    facility_id: UUID | None
    code: str
    title: str
    period_start: date | None
    period_end: date | None
    due_at: datetime | None
    status: str
    owner_user_id: UUID | None
    submitted_at: datetime | None
    external_receipt: str | None
    data: dict
    created_at: datetime
    updated_at: datetime


class ObligationUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    due_at: datetime | None = None
    owner_user_id: UUID | None = None
    data: dict | None = None


# ── Task ──────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    obligation_id: UUID | None = None
    parent_task_id: UUID | None = None
    task_type: str = "task"
    title: str
    description: str | None = None
    priority: str = "medium"
    start_at: datetime | None = None
    due_at: datetime | None = None
    assignee_user_id: UUID | None = None
    department_id: UUID | None = None


class TaskRead(OrmBase):
    id: UUID
    tenant_id: UUID
    obligation_id: UUID | None
    parent_task_id: UUID | None
    task_type: str
    title: str
    description: str | None
    status: str
    priority: str
    start_at: datetime | None
    due_at: datetime | None
    completed_at: datetime | None
    assignee_user_id: UUID | None
    department_id: UUID | None
    progress_percent: float
    created_at: datetime
    updated_at: datetime


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_at: datetime | None = None
    assignee_user_id: UUID | None = None
    progress_percent: float | None = None


# ── DeclarationTemplate ──────────────────────────────────────────────────

class DeclarationTemplateRead(OrmBase):
    id: UUID
    country_id: int
    system_code: str
    name: str
    version: str
    valid_from: date | None
    valid_to: date | None
    active: bool
    created_at: datetime
    updated_at: datetime


# ── DeclarationSubmission ─────────────────────────────────────────────────

class DeclarationSubmissionCreate(BaseModel):
    obligation_id: UUID
    template_id: UUID | None = None
    facility_id: UUID | None = None
    period_label: str | None = None
    submission_data: dict = Field(default_factory=dict)


class DeclarationSubmissionRead(OrmBase):
    id: UUID
    tenant_id: UUID
    obligation_id: UUID
    template_id: UUID | None
    facility_id: UUID | None
    period_label: str | None
    version_no: int
    status: str
    prepared_by: UUID | None
    reviewed_by: UUID | None
    submitted_by: UUID | None
    submitted_at: datetime | None
    external_folio: str | None
    submission_data: dict
    validation_result: dict
    receipt_document_id: UUID | None
    created_at: datetime
    updated_at: datetime


class DeclarationSubmissionUpdate(BaseModel):
    status: str | None = None
    submission_data: dict | None = None
    external_folio: str | None = None


class ObligationTemplateCreate(BaseModel):
    """Plantilla de obligacion del catalogo **global**.

    No lleva `tenant_id`: lo que se cree aca lo ven todas las empresas. Por eso
    el endpoint exige Admin Global.
    """

    country_id: int
    code: str
    name: str
    authority: str | None = None
    frequency_rule: str | None = None
    default_lead_days: int = Field(default=30, ge=0, le=365)
    template_config: dict = Field(default_factory=dict)


class ObligationTemplateUpdate(BaseModel):
    """`code` no esta: es la clave natural, UNIQUE global, y el seed la usa
    como destino de `ON CONFLICT`. Cambiarla romperia esa sincronizacion."""

    name: str | None = None
    authority: str | None = None
    frequency_rule: str | None = None
    default_lead_days: int | None = Field(default=None, ge=0, le=365)
    template_config: dict | None = None
    active: bool | None = None


class DeclarationTemplateCreate(BaseModel):
    """Plantilla de declaracion del catalogo **global**."""

    country_id: int
    system_code: str
    name: str
    version: str
    valid_from: date | None = None
    valid_to: date | None = None
    schema_definition: dict = Field(default_factory=dict)


class DeclarationTemplateUpdate(BaseModel):
    """`system_code` y `version` forman la unicidad: otra version es otra
    plantilla, no una edicion de esta."""

    name: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    schema_definition: dict | None = None
    active: bool | None = None
