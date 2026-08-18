from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── Country ───────────────────────────────────────────────────────────────

class CountryRead(OrmBase):
    """Catalogo estatico de referencia. **Solo lectura, y es deliberado.**

    `docs/estado-crud-base-de-datos.md` lo dice desde antes: "se consulta, no se
    administra". Lo que faltaba era la mitad positiva de esa decision — habia
    quedado sin escritura (correcto) y tambien sin lectura, asi que
    `POST /catalog/norms` pedia un `country_id` que la interfaz no tenia de
    donde sacar y crear una norma era imposible.

    Por eso no hay `CountryCreate` ni `CountryUpdate`: agregar un pais no es una
    operacion de la aplicacion.
    """

    id: int
    iso2: str
    iso3: str
    name: str
    default_timezone: str


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
    """Que norma aplica a que sector, con que nivel y por que.

    `applicability_level` es lo que decide si la norma es **obligatoria** para
    la empresa del sector (`directa`) o solo **recomendada** (`indirecta`,
    `referencial`).
    """

    norm_id: UUID
    sector_id: int
    article_id: UUID | None
    applicability_level: str
    rationale: str | None
    source: str
    confidence: float | None
    classified_by: UUID | None
    classified_at: datetime | None


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


class FacilityNormAssignmentUpdate(BaseModel):
    """Lo editable de una asignacion de norma a instalacion.

    `facility_id` y `norm_id` son la identidad del vinculo. `assigned_by` y
    `assigned_at` los escribe el servidor al resolver la asignacion, nunca el
    cuerpo: dicen quien decidio y cuando, y aceptarlos del cliente los volveria
    declarativos en vez de probatorios.
    """

    assignment_status: str | None = None
    assigned_version_id: UUID | None = None
    applicability_reason: str | None = None


class FacilityNormAssignmentCreateAnidado(BaseModel):
    """Cuerpo de `POST /facilities/{facility_id}/norms`.

    Sin `facility_id` (viene del path) ni `source`: lo que entra por este
    endpoint lo decidio una persona, asi que el servidor lo fija en 'manual'.
    Aceptarlo del cuerpo permitiria disfrazar una decision manual como si la
    hubiera sugerido el sistema.
    """

    norm_id: UUID
    assigned_version_id: UUID | None = None
    assignment_status: str = "pending_review"
    applicability_reason: str | None = None


class LegalSourceCreate(BaseModel):
    code: str
    name: str
    base_url: str | None = None


class LegalSourceUpdate(BaseModel):
    """`code` es la clave natural que usan los sincronizadores."""

    name: str | None = None
    base_url: str | None = None
    active: bool | None = None


class SectorCreate(BaseModel):
    code: str
    name: str
    parent_sector_id: int | None = None


class SectorUpdate(BaseModel):
    name: str | None = None
    parent_sector_id: int | None = None
    active: bool | None = None


# ── Clasificacion de normas por sector (RF-19) ────────────────────────────

class NormSectorWrite(BaseModel):
    """Declarar que una norma aplica a un sector.

    `rationale` es obligatorio y con minimo real: una clasificacion sin
    explicacion es indistinguible de un error de carga cuando alguien la revisa
    un ano despues, y esta se propaga a **todas** las empresas del sector.
    """

    applicability_level: str = Field(
        default="directa",
        description="directa = la debe cumplir; indirecta o referencial = se le recomienda revisar",
    )
    rationale: str = Field(min_length=10, max_length=2000)
    article_id: UUID | None = Field(
        default=None,
        description="Acota la clasificacion a un articulo, cuando solo parte de la norma aplica",
    )
