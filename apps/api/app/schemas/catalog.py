from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .base import OrmBase


# ── LegalSource ───────────────────────────────────────────────────────────

class LegalSourceRead(OrmBase):
    id: int
    country_id: int
    code: str
    name: str
    base_url: str | None
    connector_config: dict
    active: bool


# ── LegalNorm ─────────────────────────────────────────────────────────────

class LegalNormCreate(BaseModel):
    country_id: int
    source_id: int
    external_norm_id: str | None = None
    norm_type: str
    norm_number: str | None = None
    title: str
    issuing_body: str | None = None
    publication_date: date | None = None
    promulgation_date: date | None = None
    effective_from: date | None = None
    status: str = "desconocida"
    official_url: str | None = None
    subjects: list[str] = Field(default_factory=list)
    source_payload: dict = Field(default_factory=dict)


class LegalNormRead(OrmBase):
    id: UUID
    country_id: int
    source_id: int
    external_norm_id: str | None
    norm_type: str
    norm_number: str | None
    title: str
    issuing_body: str | None
    publication_date: date | None
    promulgation_date: date | None
    effective_from: date | None
    repeal_date: date | None
    status: str
    official_url: str | None
    subjects: list[str]
    last_source_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LegalNormUpdate(BaseModel):
    status: str | None = None
    official_url: str | None = None
    subjects: list[str] | None = None


# ── LegalNormVersion ──────────────────────────────────────────────────────

class LegalNormVersionCreate(BaseModel):
    norm_id: UUID
    external_version_id: str | None = None
    version_label: str | None = None
    valid_from: date
    valid_to: date | None = None
    is_current: bool = False
    content_hash: str
    full_text: str | None = None
    change_summary: str | None = None


class LegalNormVersionRead(OrmBase):
    id: UUID
    norm_id: UUID
    external_version_id: str | None
    version_label: str | None
    valid_from: date
    valid_to: date | None
    is_current: bool
    content_hash: str
    change_summary: str | None
    source_retrieved_at: datetime
    created_at: datetime
    updated_at: datetime


# ── LegalArticle ──────────────────────────────────────────────────────────

class LegalArticleCreate(BaseModel):
    norm_version_id: UUID
    parent_article_id: UUID | None = None
    external_article_id: str | None = None
    article_type: str = "article"
    article_number: str
    heading: str | None = None
    content: str
    display_order: int
    effective_from: date | None = None
    effective_to: date | None = None
    structured_content: dict = Field(default_factory=dict)


class LegalArticleRead(OrmBase):
    id: UUID
    norm_version_id: UUID
    parent_article_id: UUID | None
    external_article_id: str | None
    article_type: str
    article_number: str
    heading: str | None
    content: str
    display_order: int
    effective_from: date | None
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


# ── LegalRelation ─────────────────────────────────────────────────────────

class LegalRelationCreate(BaseModel):
    source_norm_id: UUID
    source_article_id: UUID | None = None
    target_norm_id: UUID
    target_article_id: UUID | None = None
    relation_type: str
    effective_date: date | None = None
    metadata: dict = Field(default_factory=dict)


class LegalRelationRead(OrmBase):
    id: int
    source_norm_id: UUID
    source_article_id: UUID | None
    target_norm_id: UUID
    target_article_id: UUID | None
    relation_type: str
    effective_date: date | None


# ── Sector ────────────────────────────────────────────────────────────────

class SectorRead(OrmBase):
    id: int
    country_id: int | None
    parent_id: int | None
    code: str
    name: str
    description: str | None


# ── NormSector ────────────────────────────────────────────────────────────

class NormSectorCreate(BaseModel):
    norm_id: UUID
    sector_id: int
    article_id: UUID | None = None
    applicability_level: str = "directa"
    rationale: str | None = None
    source: str = "analyst"
    confidence: float | None = None


class NormSectorRead(OrmBase):
    norm_id: UUID
    sector_id: int
    article_id: UUID | None
    applicability_level: str
    rationale: str | None
    source: str
    confidence: float | None


# ── NormSyncRun ───────────────────────────────────────────────────────────

class NormSyncRunRead(OrmBase):
    id: int
    source_id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    norms_created: int
    norms_updated: int
    versions_created: int
    error_detail: str | None


# ── FacilityNormAssignment ────────────────────────────────────────────────

class FacilityNormAssignmentCreate(BaseModel):
    facility_id: UUID
    norm_id: UUID
    assigned_version_id: UUID | None = None
    assignment_status: str = "pending_review"
    applicability_reason: str | None = None
    source: str = "manual"


class FacilityNormAssignmentRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID
    norm_id: UUID
    assigned_version_id: UUID | None
    assignment_status: str
    applicability_reason: str | None
    assigned_by: UUID | None
    assigned_at: datetime
    source: str
    created_at: datetime
    updated_at: datetime
