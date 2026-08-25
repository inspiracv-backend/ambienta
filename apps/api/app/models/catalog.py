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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class LegalSource(Base):
    __tablename__ = "legal_sources"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("countries.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    connector_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class LegalNorm(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "legal_norms"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "external_norm_id", name="uq_legal_norms_source_external"
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    country_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("countries.id"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("legal_sources.id"), nullable=False
    )
    external_norm_id: Mapped[str | None] = mapped_column(String(80))
    norm_type: Mapped[str] = mapped_column(String(80), nullable=False)
    norm_number: Mapped[str | None] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    issuing_body: Mapped[str | None] = mapped_column(String(240))
    publication_date: Mapped[date | None] = mapped_column(Date)
    promulgation_date: Mapped[date | None] = mapped_column(Date)
    effective_from: Mapped[date | None] = mapped_column(Date)
    repeal_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="desconocida"
    )
    official_url: Mapped[str | None] = mapped_column(String(700))
    subjects: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    source_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    last_source_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    source = relationship("LegalSource", lazy="select")
    versions = relationship("LegalNormVersion", back_populates="norm", lazy="select")


class LegalNormVersion(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "legal_norm_versions"
    __table_args__ = (
        UniqueConstraint("norm_id", "content_hash", name="uq_norm_versions_hash"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_norm_versions_vigencia",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    norm_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_norms.id", ondelete="CASCADE"), nullable=False
    )
    external_version_id: Mapped[str | None] = mapped_column(String(100))
    version_label: Mapped[str | None] = mapped_column(String(160))
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    full_text: Mapped[str | None] = mapped_column(Text)
    xml_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    change_summary: Mapped[str | None] = mapped_column(Text)
    source_retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    norm = relationship("LegalNorm", back_populates="versions", lazy="select")
    articles = relationship("LegalArticle", back_populates="norm_version", lazy="select")


class LegalArticle(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "legal_articles"
    __table_args__ = (
        UniqueConstraint(
            "norm_version_id", "external_article_id",
            name="uq_legal_articles_external",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    norm_version_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_norm_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_article_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_articles.id")
    )
    external_article_id: Mapped[str | None] = mapped_column(String(120))
    article_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="article"
    )
    article_number: Mapped[str] = mapped_column(String(40), nullable=False)
    heading: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    structured_content: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    norm_version = relationship(
        "LegalNormVersion", back_populates="articles", lazy="select"
    )
    parent = relationship(
        "LegalArticle", remote_side="LegalArticle.id", lazy="select"
    )


class LegalRelation(Base):
    __tablename__ = "legal_relations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_norm_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_norms.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_article_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_articles.id")
    )
    target_norm_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_norms.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_article_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_articles.id")
    )
    relation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    country_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("countries.id")
    )
    parent_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("sectors.id")
    )
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    parent = relationship("Sector", remote_side="Sector.id", lazy="select")


class NormSector(Base):
    __tablename__ = "norm_sectors"

    norm_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_norms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sector_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("sectors.id"), primary_key=True
    )
    article_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_articles.id")
    )
    applicability_level: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="directa"
    )
    rationale: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="analyst"
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    # Quien clasifico y cuando. Una clasificacion errada se propaga a TODAS las
    # empresas del sector: sin autor no hay a quien preguntarle por que.
    classified_by: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True))
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NormSyncRun(Base):
    __tablename__ = "norm_sync_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("legal_sources.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="running"
    )
    request_parameters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    response_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    norms_created: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    norms_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    versions_created: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    error_detail: Mapped[str | None] = mapped_column(Text)


class FacilityNormAssignment(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "facility_norm_assignments"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    facility_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facilities.id", ondelete="CASCADE"),
        nullable=False,
    )
    norm_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_norms.id"), nullable=False
    )
    assigned_version_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_norm_versions.id")
    )
    assignment_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="pending_review"
    )
    applicability_reason: Mapped[str | None] = mapped_column(Text)
    assigned_by: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="manual"
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class RetcSystem(Base, SoftDeleteMixin):
    """Un portal del ecosistema RETC ante el que se declara (ADR-004, #103).

    **No es un `Sector`.** `Sector` es el rubro economico de la empresa (CIIU) y
    responde "a que se dedica"; esto responde "donde reporta". Son dimensiones
    ortogonales, y el repo usa el numero 21 para las dos sin relacion.

    Catalogo global: **sin `tenant_id`**, como `LegalNorm` y `Sector`. Los
    portales son los mismos para todas las empresas, asi que copiarlos por
    empresa obligaria a aplicar cada resolucion del MMA N veces.
    """

    __tablename__ = "retc_systems"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    organismo: Mapped[str] = mapped_column(String(60), nullable=False)
    familia: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default="sectorial"
    )
    #: `variable_rca` es un valor de verdad, no un relleno: ADR-004 dice que
    #: SSA, SRCA y SIVEM dependen de la RCA de cada instalacion y **no se
    #: pueden autogenerar**. Nace `None` porque el portal oficial lista los
    #: sistemas pero no su calendario, y las fechas cambian por resolucion cada
    #: ano: inventarla generaria vencimientos falsos.
    periodicidad: Mapped[str | None] = mapped_column(String(16))
    url_oficial: Mapped[str | None] = mapped_column(Text)
    #: De donde salio la fila. Obligatoria a proposito.
    fuente: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    #: `false` hasta que negocio confirme la lista. Ver `db/12_reportabilidad_retc.sql`.
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # `created_at`/`updated_at` a mano y **sin `TimestampMixin`**: ese mixin
    # trae ademas `created_by` y `updated_by`, y aca no hay usuario que crear.
    # Un portal del Estado no lo da de alta nadie del sistema — llega por
    # resolucion y se siembra con una migracion.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FacilityRetcReporting(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Que sistemas del RETC le tocan a una instalacion (ADR-004, #102).

    Es el nucleo del modulo: hoy un especialista lo determina a mano cruzando
    articulos de la RCA con los portales que aplican, y es trabajo de dias por
    instalacion nueva.

    **`condicion` no es opcional cuando el estado es `condicional`** — lo exige
    un CHECK. Un "aplica si se cumple algo" sin decir que algo no se puede
    revisar un ano despues sin repetir la entrevista entera.
    """

    __tablename__ = "facility_retc_reporting"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    facility_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facilities.id", ondelete="CASCADE"),
        nullable=False,
    )
    retc_system_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("retc_systems.id"), nullable=False
    )
    estado: Mapped[str] = mapped_column(String(16), nullable=False, server_default="no")
    condicion: Mapped[str | None] = mapped_column(Text)
    #: Las respuestas del wizard que llevaron a este estado. Se guardan aunque
    #: ya esten resumidas en `estado`: sin ellas la decision no es auditable.
    variables: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    responsable_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    notas: Mapped[str | None] = mapped_column(Text)
