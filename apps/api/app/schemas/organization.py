from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .base import OrmBase


# ── Country ───────────────────────────────────────────────────────────────

class CountryRead(OrmBase):
    id: int
    iso2: str
    iso3: str
    name: str
    default_timezone: str


# ── Tenant ────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    country_id: int
    parent_tenant_id: UUID | None = None
    tenant_type: str = "company"
    rut_tax_id: str
    legal_name: str
    trade_name: str | None = None
    business_activity: str | None = None
    settings: dict = Field(default_factory=dict)


class TenantRead(OrmBase):
    id: UUID
    country_id: int
    parent_tenant_id: UUID | None
    tenant_type: str
    rut_tax_id: str
    legal_name: str
    trade_name: str | None
    business_activity: str | None
    status: str
    settings: dict
    created_at: datetime
    updated_at: datetime


class TenantUpdate(BaseModel):
    legal_name: str | None = None
    trade_name: str | None = None
    business_activity: str | None = None
    status: str | None = None
    settings: dict | None = None


# ── Facility ──────────────────────────────────────────────────────────────

class FacilityCreate(BaseModel):
    code: str
    name: str
    facility_type: str
    address: str | None = None
    region_code: str | None = None
    commune_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    environmental_identifiers: dict = Field(default_factory=dict)


class FacilityRead(OrmBase):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    facility_type: str
    address: str | None
    region_code: str | None
    commune_code: str | None
    latitude: float | None
    longitude: float | None
    environmental_identifiers: dict
    active: bool
    created_at: datetime
    updated_at: datetime


class FacilityUpdate(BaseModel):
    name: str | None = None
    facility_type: str | None = None
    address: str | None = None
    region_code: str | None = None
    commune_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    environmental_identifiers: dict | None = None
    active: bool | None = None


# ── Department ────────────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    facility_id: UUID | None = None
    parent_department_id: UUID | None = None
    code: str
    name: str


class DepartmentRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    parent_department_id: UUID | None
    code: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentUpdate(BaseModel):
    name: str | None = None
    facility_id: UUID | None = None
    parent_department_id: UUID | None = None
    active: bool | None = None


# ── User ──────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    department_id: UUID | None = None
    rut_tax_id: str | None = None
    email: str
    full_name: str
    user_type: str
    preferences: dict = Field(default_factory=dict)


class UserRead(OrmBase):
    id: UUID
    tenant_id: UUID
    department_id: UUID | None
    rut_tax_id: str | None
    email: str
    full_name: str
    user_type: str
    status: str
    preferences: dict
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
    department_id: UUID | None = None
    status: str | None = None
    preferences: dict | None = None


# ── Role ──────────────────────────────────────────────────────────────────

class RoleCreate(BaseModel):
    code: str
    name: str
    is_system: bool = False
    description: str | None = None


class RoleRead(OrmBase):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    is_system: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# ── Permission ────────────────────────────────────────────────────────────

class PermissionRead(OrmBase):
    id: int
    code: str
    module: str
    description: str


# ── RolePermission ────────────────────────────────────────────────────────

class RolePermissionCreate(BaseModel):
    role_id: UUID
    permission_id: int
    granted: bool = True


class RolePermissionRead(OrmBase):
    role_id: UUID
    permission_id: int
    granted: bool


# ── UserRole ──────────────────────────────────────────────────────────────

class UserRoleCreate(BaseModel):
    user_id: UUID
    role_id: UUID
    facility_id: UUID | None = None
    department_id: UUID | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class UserRoleRead(OrmBase):
    user_id: UUID
    role_id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    department_id: UUID | None
    valid_from: datetime
    valid_to: datetime | None


# ── Process ───────────────────────────────────────────────────────────────

class ProcessCreate(BaseModel):
    department_id: UUID | None = None
    parent_process_id: UUID | None = None
    code: str
    name: str
    process_type: str
    description: str | None = None
    responsible_user_id: UUID | None = None
    inputs: list = Field(default_factory=list)
    outputs: list = Field(default_factory=list)
    display_order: int = 0


class ProcessRead(OrmBase):
    id: UUID
    tenant_id: UUID
    department_id: UUID | None
    parent_process_id: UUID | None
    code: str
    name: str
    process_type: str
    description: str | None
    responsible_user_id: UUID | None
    inputs: list
    outputs: list
    display_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


class ProcessUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    responsible_user_id: UUID | None = None
    inputs: list | None = None
    outputs: list | None = None
    display_order: int | None = None
    active: bool | None = None


# ── FacilityProcess ───────────────────────────────────────────────────────

class FacilityProcessCreate(BaseModel):
    facility_id: UUID
    process_id: UUID
    is_primary: bool = False
    scope_notes: str | None = None
    active_from: date | None = None
    active_to: date | None = None


class FacilityProcessRead(OrmBase):
    facility_id: UUID
    process_id: UUID
    tenant_id: UUID
    is_primary: bool
    scope_notes: str | None
    active_from: date | None
    active_to: date | None
    created_at: datetime
    updated_at: datetime


# ── Contract ──────────────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    manager_tenant_id: UUID
    client_tenant_id: UUID
    contract_number: str
    title: str
    start_date: date
    end_date: date | None = None
    scope: dict = Field(default_factory=dict)
    terms_snapshot: dict = Field(default_factory=dict)


class ContractRead(OrmBase):
    id: UUID
    tenant_id: UUID
    manager_tenant_id: UUID
    client_tenant_id: UUID
    contract_number: str
    title: str
    status: str
    start_date: date
    end_date: date | None
    scope: dict
    terms_snapshot: dict
    created_at: datetime
    updated_at: datetime


class ContractUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    end_date: date | None = None
    scope: dict | None = None
