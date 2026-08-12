from datetime import date
from uuid import UUID as PyUUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class EnvironmentalAspect(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "environmental_aspects"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    facility_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facilities.id", ondelete="CASCADE"),
        nullable=False,
    )
    process_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processes.id")
    )
    article_compliance_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_compliance.id")
    )
    activity: Mapped[str] = mapped_column(String(240), nullable=False)
    aspect: Mapped[str] = mapped_column(String(240), nullable=False)
    impact_type: Mapped[str] = mapped_column(String(120), nullable=False)
    operating_condition: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="normal"
    )
    severity_score: Mapped[int | None] = mapped_column(SmallInteger)
    frequency_score: Mapped[int | None] = mapped_column(SmallInteger)
    legal_score: Mapped[int | None] = mapped_column(SmallInteger)
    total_score: Mapped[int | None] = mapped_column(Integer)
    significance: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    responsible_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    controls: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )


class RiskOpportunity(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "risks_opportunities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_risks_opportunities_code"),
        CheckConstraint(
            "origin <> 'environmental_aspect' OR environmental_aspect_id IS NOT NULL",
            name="ck_risks_origen_aspecto",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    environmental_aspect_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("environmental_aspects.id")
    )
    action_plan_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("action_plans.id")
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="medium"
    )
    treatment: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="identified"
    )
    owner_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    review_date: Mapped[date | None] = mapped_column(Date)


class RegulatedEquipment(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "regulated_equipment"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    facility_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facilities.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    registration_authority: Mapped[str | None] = mapped_column(String(40))
    registration_number: Mapped[str | None] = mapped_column(String(80))
    registration_expires_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="operational"
    )
    technical_specs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )


class EquipmentOperator(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "equipment_operators"

    equipment_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulated_equipment.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    certification_class: Mapped[str | None] = mapped_column(String(40))
    certification_number: Mapped[str | None] = mapped_column(String(80))
    certification_expires_at: Mapped[date | None] = mapped_column(Date)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
