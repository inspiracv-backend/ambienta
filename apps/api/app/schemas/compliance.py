from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── TenantLegalMatrix ─────────────────────────────────────────────────────

class TenantLegalMatrixCreate(BaseModel):
    name: str
    period_year: int
    facility_id: UUID | None = None
    scope_definition: dict = Field(default_factory=dict)


class TenantLegalMatrixRead(OrmBase):
    id: UUID
    tenant_id: UUID
    name: str
    period_year: int
    facility_id: UUID | None
    status: str
    version_no: int
    approved_at: datetime | None
    approved_by: UUID | None
    scope_definition: dict
    created_at: datetime
    updated_at: datetime


class TenantLegalMatrixUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    scope_definition: dict | None = None


# ── MatrixNorm ────────────────────────────────────────────────────────────

class MatrixNormCreate(BaseModel):
    matrix_id: UUID
    norm_id: UUID
    selected_version_id: UUID
    sector_id: int | None = None
    applicability: str = "pending_analysis"
    applicability_reason: str | None = None
    owner_user_id: UUID | None = None
    review_frequency: str = "annual"
    next_review_date: datetime | None = None


class MatrixNormRead(OrmBase):
    id: UUID
    tenant_id: UUID
    matrix_id: UUID
    norm_id: UUID
    selected_version_id: UUID
    sector_id: int | None
    applicability: str
    applicability_reason: str | None
    owner_user_id: UUID | None
    review_frequency: str
    next_review_date: datetime | None
    snapshot: dict
    created_at: datetime
    updated_at: datetime


class MatrixNormUpdate(BaseModel):
    applicability: str | None = None
    applicability_reason: str | None = None
    owner_user_id: UUID | None = None
    review_frequency: str | None = None
    next_review_date: datetime | None = None


# ── ArticleCompliance ─────────────────────────────────────────────────────

class ArticleComplianceCreate(BaseModel):
    matrix_norm_id: UUID
    article_id: UUID
    facility_id: UUID | None = None
    department_id: UUID | None = None
    compliance_status: str = "pending"
    compliance_method: str | None = None
    assessment_reason: str | None = None
    risk_level: str | None = None
    responsible_user_id: UUID | None = None


class ArticleComplianceRead(OrmBase):
    id: UUID
    tenant_id: UUID
    matrix_norm_id: UUID
    article_id: UUID
    facility_id: UUID | None
    department_id: UUID | None
    compliance_status: str
    compliance_method: str | None
    assessment_reason: str | None
    risk_level: str | None
    responsible_user_id: UUID | None
    assessed_at: datetime | None
    assessed_by: UUID | None
    approved_at: datetime | None
    approved_by: UUID | None
    attributes: dict
    row_version: int
    created_at: datetime
    updated_at: datetime


class ArticleComplianceUpdate(BaseModel):
    compliance_status: str | None = None
    compliance_method: str | None = None
    assessment_reason: str | None = None
    risk_level: str | None = None
    responsible_user_id: UUID | None = None
    attributes: dict | None = None


# ── Normativa aplicable (RF-19) ───────────────────────────────────────────

class NormaAplicableRead(BaseModel):
    """Una norma que le corresponde a la empresa, **y por que le corresponde**.

    `sector_id` y `applicability_level` no son adorno: son la respuesta a la
    primera pregunta de un fiscalizador — como determinaron que esta norma les
    aplica.
    """

    norm_id: UUID
    title: str
    norm_type: str
    norm_number: str | None
    sector_id: int
    applicability_level: str
    rationale: str | None


class NormativaAplicableRead(BaseModel):
    """El calculo completo, con el motivo cuando viene vacio.

    `estado` existe porque una lista vacia tiene **dos causas opuestas** y
    ninguna significa "esta empresa no tiene obligaciones":

    - `sin_perfil`: falta que la empresa declare su sector
    - `sector_sin_clasificar`: falta que nosotros clasifiquemos las normas
    - `con_normativa`: hay resultado

    Devolver solo la lista dejaria que la pantalla mostrara "0 normas" en los
    tres casos, y el mas peligroso se lee como estar en regla.
    """

    estado: str
    sector_id: int | None
    obligatorias: list[NormaAplicableRead]
    recomendadas: list[NormaAplicableRead]
    total: int


class SincronizacionRead(BaseModel):
    """Que cambio al sincronizar la matriz.

    Se devuelven los numeros y no un "ok" porque la promesa del servicio es
    verificable: **`evaluaciones_conservadas` no puede bajar**. Si baja, algo
    borro trabajo hecho, y eso tiene que poder verse sin abrir la base.
    """

    normas_agregadas: int
    normas_ya_estaban: int
    normas_marcadas_no_aplicables: int
    articulos_agregados: int
    evaluaciones_conservadas: int
    sin_calcular: str | None = Field(
        default=None,
        description=(
            "Presente cuando el calculo no pudo correr: 'sin_perfil' si la "
            "empresa no declaro su sector, 'sector_sin_clasificar' si nadie "
            "clasifico normas para el suyo. En ese caso NO se toco nada"
        ),
    )
