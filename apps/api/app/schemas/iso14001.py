from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── EnvironmentalAspect ───────────────────────────────────────────────────

class EnvironmentalAspectCreate(BaseModel):
    facility_id: UUID
    process_id: UUID | None = None
    article_compliance_id: UUID | None = None
    activity: str
    aspect: str
    impact_type: str
    operating_condition: str = "normal"
    severity_score: int | None = None
    frequency_score: int | None = None
    legal_score: int | None = None
    responsible_user_id: UUID | None = None
    controls: list = Field(default_factory=list)


class EnvironmentalAspectRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID
    process_id: UUID | None
    article_compliance_id: UUID | None
    activity: str
    aspect: str
    impact_type: str
    operating_condition: str
    severity_score: int | None
    frequency_score: int | None
    legal_score: int | None
    total_score: int | None
    significance: str
    responsible_user_id: UUID | None
    controls: list
    created_at: datetime
    updated_at: datetime


class EnvironmentalAspectUpdate(BaseModel):
    activity: str | None = None
    aspect: str | None = None
    impact_type: str | None = None
    operating_condition: str | None = None
    severity_score: int | None = None
    frequency_score: int | None = None
    legal_score: int | None = None
    responsible_user_id: UUID | None = None
    controls: list | None = None


# ── RiskOpportunity ───────────────────────────────────────────────────────

class RiskOpportunityCreate(BaseModel):
    facility_id: UUID | None = None
    environmental_aspect_id: UUID | None = None
    action_plan_id: UUID | None = None
    code: str
    entry_type: str
    description: str
    origin: str
    risk_level: str = "medium"
    treatment: str | None = None
    owner_user_id: UUID | None = None
    review_date: date | None = None


class RiskOpportunityRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    environmental_aspect_id: UUID | None
    action_plan_id: UUID | None
    code: str
    entry_type: str
    description: str
    origin: str
    risk_level: str
    treatment: str | None
    status: str
    owner_user_id: UUID | None
    review_date: date | None
    created_at: datetime
    updated_at: datetime


class RiskOpportunityUpdate(BaseModel):
    description: str | None = None
    risk_level: str | None = None
    treatment: str | None = None
    status: str | None = None
    owner_user_id: UUID | None = None
    review_date: date | None = None


# ── RegulatedEquipment ────────────────────────────────────────────────────

class RegulatedEquipmentCreate(BaseModel):
    facility_id: UUID
    name: str
    equipment_type: str
    brand: str | None = None
    model: str | None = None
    registration_authority: str | None = None
    registration_number: str | None = None
    registration_expires_at: date | None = None
    technical_specs: dict = Field(default_factory=dict)


class RegulatedEquipmentRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID
    name: str
    equipment_type: str
    brand: str | None
    model: str | None
    registration_authority: str | None
    registration_number: str | None
    registration_expires_at: date | None
    status: str
    technical_specs: dict
    created_at: datetime
    updated_at: datetime


class RegulatedEquipmentUpdate(BaseModel):
    name: str | None = None
    equipment_type: str | None = None
    brand: str | None = None
    model: str | None = None
    registration_authority: str | None = None
    registration_number: str | None = None
    registration_expires_at: date | None = None
    status: str | None = None
    technical_specs: dict | None = None


# ── EquipmentOperator ─────────────────────────────────────────────────────

class EquipmentOperatorCreate(BaseModel):
    equipment_id: UUID
    user_id: UUID
    certification_class: str | None = None
    certification_number: str | None = None
    certification_expires_at: date | None = None
    is_primary: bool = False


class EquipmentOperatorRead(OrmBase):
    id: UUID | None = None
    equipment_id: UUID
    user_id: UUID
    tenant_id: UUID
    certification_class: str | None
    certification_number: str | None
    certification_expires_at: date | None
    is_primary: bool
    created_at: datetime
    updated_at: datetime
