from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class TenantLegalMatrix(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenant_legal_matrices"
    __table_args__ = (
        CheckConstraint(
            "(status = 'approved') = (approved_at IS NOT NULL)",
            name="ck_matrices_aprobacion",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    period_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="draft"
    )
    version_no: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    scope_definition: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    norms = relationship("MatrixNorm", back_populates="matrix", lazy="select")


class MatrixNorm(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "matrix_norms"
    __table_args__ = (
        UniqueConstraint("matrix_id", "norm_id", name="uq_matrix_norms"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    matrix_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_legal_matrices.id", ondelete="CASCADE"),
        nullable=False,
    )
    norm_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_norms.id"), nullable=False
    )
    selected_version_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_norm_versions.id"), nullable=False
    )
    sector_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("sectors.id")
    )
    applicability: Mapped[str] = mapped_column(
        String(28), nullable=False, server_default="pending_analysis"
    )
    applicability_reason: Mapped[str | None] = mapped_column(Text)
    # Como entro esta norma a la matriz. Importa porque un recalculo **no puede
    # quitar** lo que alguien agrego a mano: que el calculo no la encuentre no
    # significa que no aplique — puede venir de un contrato o de la RCA.
    # Ver db/08_perfil_normativo.sql.
    inclusion_source: Mapped[str | None] = mapped_column(String(16))
    owner_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    review_frequency: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="annual"
    )
    next_review_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    matrix = relationship("TenantLegalMatrix", back_populates="norms", lazy="select")


class ArticleCompliance(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "article_compliance"
    __table_args__ = (
        UniqueConstraint(
            "matrix_norm_id", "article_id", "facility_id",
            name="uq_article_compliance",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    matrix_norm_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("matrix_norms.id", ondelete="CASCADE"),
        nullable=False,
    )
    article_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_articles.id"), nullable=False
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    department_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    compliance_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="pending"
    )
    compliance_method: Mapped[str | None] = mapped_column(Text)
    # El enlace a la evidencia (db/16). **Faltaba, y `evaluate_article()` se
    # lo asignaba igual:** SQLAlchemy deja poner atributos sueltos en una
    # instancia y no los persiste, asi que el endpoint respondia 200 y el
    # dato se perdia sin que nada avisara.
    evidence_url: Mapped[str | None] = mapped_column(Text)
    assessment_reason: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[str | None] = mapped_column(String(16))
    responsible_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessed_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    attributes: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    row_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
