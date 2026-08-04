from datetime import date, datetime
from uuid import UUID as PyUUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    iso2: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    iso3: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    default_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="America/Santiago"
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenants"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    country_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("countries.id"), nullable=False
    )
    parent_tenant_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )
    tenant_type: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="company"
    )
    rut_tax_id: Mapped[str] = mapped_column(String(32), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(180))
    business_activity: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="trial"
    )
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    country = relationship("Country", lazy="joined")
    parent = relationship("Tenant", remote_side="Tenant.id", lazy="select")
    facilities = relationship("Facility", back_populates="tenant", lazy="select")
    users = relationship("User", back_populates="tenant", lazy="select")


class Facility(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "facilities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_facilities_tenant_code"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(40), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    region_code: Mapped[str | None] = mapped_column(String(20))
    commune_code: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    environmental_identifiers: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    tenant = relationship("Tenant", back_populates="facilities", lazy="select")


class Department(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    parent_department_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    facility = relationship("Facility", lazy="select")
    parent = relationship("Department", remote_side="Department.id", lazy="select")


class User(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    department_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    rut_tax_id: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    user_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="invited"
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    preferences: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant = relationship("Tenant", back_populates="users", lazy="select")
    department = relationship("Department", lazy="select")


class Role(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_roles_tenant_code"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    description: Mapped[str | None] = mapped_column(Text)

    permissions = relationship(
        "RolePermission", back_populates="role", lazy="select"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("permissions.id"), primary_key=True
    )
    granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    role = relationship("Role", back_populates="permissions", lazy="select")
    permission = relationship("Permission", lazy="joined")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_user_roles_vigencia",
        ),
    )

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    department_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", lazy="select")
    role = relationship("Role", lazy="select")


class Process(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "processes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_processes_tenant_code"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    department_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    parent_process_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processes.id")
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    process_type: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    responsible_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    inputs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    outputs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    parent = relationship("Process", remote_side="Process.id", lazy="select")


class FacilityProcess(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "facility_processes"

    facility_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facilities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    process_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    scope_notes: Mapped[str | None] = mapped_column(Text)
    active_from: Mapped[date | None] = mapped_column(Date)
    active_to: Mapped[date | None] = mapped_column(Date)


class Contract(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint(
            "manager_tenant_id", "contract_number", name="uq_contracts_manager_number"
        ),
        CheckConstraint(
            "manager_tenant_id <> client_tenant_id", name="ck_contracts_partes"
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date", name="ck_contracts_fechas"
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    manager_tenant_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    client_tenant_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    contract_number: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="draft"
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    terms_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
