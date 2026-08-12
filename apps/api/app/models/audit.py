from datetime import date, datetime
from uuid import UUID as PyUUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class Audit(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "audits"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_audits_tenant_code"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    audit_type: Mapped[str] = mapped_column(String(24), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    lead_auditor_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="planned"
    )
    criteria: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    items = relationship("AuditItem", back_populates="audit", lazy="select")
    participants = relationship("AuditParticipant", back_populates="audit", lazy="select")


class AuditItem(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "audit_items"
    __table_args__ = (
        UniqueConstraint("audit_id", "sequence", name="uq_audit_items_seq"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    article_compliance_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_compliance.id")
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="pending"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    auditor_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    audit = relationship("Audit", back_populates="items", lazy="select")


class AuditParticipant(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "audit_participants"

    audit_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    external_name: Mapped[str | None] = mapped_column(String(180))
    external_email: Mapped[str | None] = mapped_column(CITEXT)
    participant_role: Mapped[str] = mapped_column(String(32), nullable=False)
    attendance_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="invited"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    audit = relationship("Audit", back_populates="participants", lazy="select")


class Nonconformity(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "nonconformities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_nonconformities_tenant_code"),
        CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL)",
            name="ck_nonconformities_cierre",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    audit_item_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_items.id")
    )
    article_compliance_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_compliance.id")
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="open"
    )
    record_type: Mapped[str | None] = mapped_column(String(24))
    detection_origin: Mapped[str | None] = mapped_column(String(24))
    root_cause_answers: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    improvement_stages: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    detected_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    owner_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closure_notes: Mapped[str | None] = mapped_column(Text)

    action_plans = relationship("ActionPlan", back_populates="nonconformity", lazy="select")


class ActionPlan(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "action_plans"
    __table_args__ = (
        CheckConstraint(
            "article_compliance_id IS NOT NULL OR nonconformity_id IS NOT NULL",
            name="ck_action_plans_origen",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    article_compliance_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_compliance.id")
    )
    nonconformity_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nonconformities.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="draft"
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="medium"
    )
    owner_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    target_date: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    success_criteria: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    nonconformity = relationship(
        "Nonconformity", back_populates="action_plans", lazy="select"
    )


class EntityStatusHistory(Base, TenantMixin):
    __tablename__ = "entity_status_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
