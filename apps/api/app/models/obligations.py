from datetime import date, datetime
from uuid import UUID as PyUUID

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class ObligationTemplate(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "obligation_templates"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    country_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("countries.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    authority: Mapped[str | None] = mapped_column(String(200))
    frequency_rule: Mapped[str | None] = mapped_column(String(500))
    default_lead_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="30"
    )
    template_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Obligation(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "obligations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_obligations_tenant_code"),
        CheckConstraint(
            "period_end IS NULL OR period_start IS NULL OR period_end >= period_start",
            name="ck_obligations_periodo",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    template_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligation_templates.id")
    )
    matrix_norm_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matrix_norms.id")
    )
    article_compliance_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_compliance.id")
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="draft"
    )
    owner_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_receipt: Mapped[str | None] = mapped_column(String(160))
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    tasks = relationship("Task", back_populates="obligation", lazy="select")


class Task(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tasks"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    obligation_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id", ondelete="CASCADE")
    )
    parent_task_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    task_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="task"
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="todo"
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="medium"
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    department_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    progress_percent: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    obligation = relationship("Obligation", back_populates="tasks", lazy="select")
    parent = relationship("Task", remote_side="Task.id", lazy="select")


class DeclarationTemplate(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "declaration_templates"
    __table_args__ = (
        UniqueConstraint("system_code", "version", name="uq_declaration_templates"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    country_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("countries.id"), nullable=False
    )
    system_code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    schema_definition: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    workbook_structure: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    source_document_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class DeclarationSubmission(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "declaration_submissions"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    obligation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("declaration_templates.id")
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    period_label: Mapped[str | None] = mapped_column(String(80))
    version_no: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="draft"
    )
    prepared_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    reviewed_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    submitted_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_folio: Mapped[str | None] = mapped_column(String(160))
    submission_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    validation_result: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    receipt_document_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
