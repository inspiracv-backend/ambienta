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
    SmallInteger,
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
    #: Con que metodologia del catalogo de la empresa se analizo la causa.
    #: `root_cause_answers` guarda las respuestas y no como se llego a ellas, y
    #: las de un Ishikawa no se leen igual que las de un 5 porques.
    root_cause_methodology_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("improvement_methodologies.id")
    )
    improvement_stages: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    #: Solo para `salida_no_conforme` (ISO 9001 8.7). La base exige SKU y lote
    #: cuando el tipo lo pide, y que no aparezca en otro tipo.
    product_data: Mapped[dict | None] = mapped_column(JSONB)
    #: Solo para `reclamo` (ISO 9001 9.1.2). Exige cliente y canal.
    complaint_data: Mapped[dict | None] = mapped_column(JSONB)
    #: Para `riesgo` y `oportunidad` (6.1): el registro del que salio.
    risk_opportunity_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True))
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


class ImprovementSeverity(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Un nivel de la escala de severidad de esta empresa (RF-100).

    **Se monta encima del CHECK de `nonconformities.severity`, no lo
    reemplaza.** El `code` es el valor que se escribe en esa columna; lo que la
    empresa configura es como se llama, en que orden va y en cuantos dias se
    cierra un hallazgo de ese nivel.
    """

    __tablename__ = "improvement_severities"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    #: **NULL significa que la empresa no declaro plazo**, y entonces nadie
    #: calcula `due_date`. No es lo mismo que cero, que la base rechaza: cero
    #: dias es un plazo imposible, no la ausencia de uno.
    days_to_close: Mapped[int | None] = mapped_column(SmallInteger)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )


class ImprovementMethodology(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Una metodologia de analisis de causa de esta empresa (RF-100, RF-35)."""

    __tablename__ = "improvement_methodologies"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: **La forma decide que datos exige el analisis.** La empresa le pone el
    #: nombre que quiera; la forma tiene que ser una de las que el sistema sabe
    #: pedir y mostrar.
    shape: Mapped[str] = mapped_column(String(30), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
