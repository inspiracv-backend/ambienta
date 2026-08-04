from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── TenantLegalMatrix ─────────────────────────────────────────────────────

class TenantLegalMatrixCreate(BaseModel):
    name: str
    period_year: int
    facility_id: UUID | None = None
    scope_definition: dict = Field(default_factory=dict)


class TenantLegalMatrixRead(OrmBase):
    id: UUID
    tenant_id: UUID
    name: str
    period_year: int
    facility_id: UUID | None
    status: str
    version_no: int
    approved_at: datetime | None
    approved_by: UUID | None
    scope_definition: dict
    created_at: datetime
    updated_at: datetime


class TenantLegalMatrixUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    scope_definition: dict | None = None


# ── MatrixNorm ────────────────────────────────────────────────────────────

class MatrixNormCreate(BaseModel):
    matrix_id: UUID
    norm_id: UUID
    selected_version_id: UUID
    sector_id: int | None = None
    applicability: str = "pending_analysis"
    applicability_reason: str | None = None
    owner_user_id: UUID | None = None
    review_frequency: str = "annual"
    next_review_date: datetime | None = None


class MatrixNormRead(OrmBase):
    id: UUID
    tenant_id: UUID
    matrix_id: UUID
    norm_id: UUID
    selected_version_id: UUID
    sector_id: int | None
    applicability: str
    applicability_reason: str | None
    owner_user_id: UUID | None
    review_frequency: str
    next_review_date: datetime | None
    snapshot: dict
    created_at: datetime
    updated_at: datetime


class MatrixNormUpdate(BaseModel):
    applicability: str | None = None
    applicability_reason: str | None = None
    owner_user_id: UUID | None = None
    review_frequency: str | None = None
    next_review_date: datetime | None = None


# ── ArticleCompliance ─────────────────────────────────────────────────────

class ArticleComplianceCreate(BaseModel):
    matrix_norm_id: UUID
    article_id: UUID
    facility_id: UUID | None = None
    department_id: UUID | None = None
    compliance_status: str = "pending"
    compliance_method: str | None = None
    assessment_reason: str | None = None
    risk_level: str | None = None
    responsible_user_id: UUID | None = None


class ArticleComplianceRead(OrmBase):
    id: UUID
    tenant_id: UUID
    matrix_norm_id: UUID
    article_id: UUID
    facility_id: UUID | None
    department_id: UUID | None
    compliance_status: str
    compliance_method: str | None
    assessment_reason: str | None
    risk_level: str | None
    responsible_user_id: UUID | None
    assessed_at: datetime | None
    assessed_by: UUID | None
    approved_at: datetime | None
    approved_by: UUID | None
    attributes: dict
    row_version: int
    created_at: datetime
    updated_at: datetime


class ArticleComplianceUpdate(BaseModel):
    compliance_status: str | None = None
    compliance_method: str | None = None
    assessment_reason: str | None = None
    risk_level: str | None = None
    responsible_user_id: UUID | None = None
    attributes: dict | None = None
