"""
Modelos de las respuestas del backend.

Escritos a partir del `openapi.json` congelado el 02/09 y del handoff del 08/09. Cuando esté
disponible el spec del 08/09, este archivo se regenera con:

    datamodel-codegen --input openapi.json --output modelos_generados.py \
        --output-model-type pydantic_v2.BaseModel

y se compara. Mientras tanto, `extra="allow"` hace que un campo nuevo del backend no rompa la
lectura, y los campos que el servicio usa están declarados: si el backend los cambia de nombre,
la validación falla en la prueba de contrato y no en producción.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


# -- identidad ---------------------------------------------------------------


class Usuario(_Base):
    id: UUID
    clerk_id: str | None = None
    email: str | None = None
    nombre: str | None = None
    tipo: str | None = None  # "platform_admin" para el Admin Global


class Empresa(_Base):
    id: UUID
    nombre: str
    sector_id: int | None = None
    tramo: str | None = None


class Me(_Base):
    """GET /me. En modo desarrollo `usuario` es null y `permisos` viene vacío."""

    modo_desarrollo: bool = False
    usuario: Usuario | None = None
    empresa: Empresa | None = None
    roles: list[str] = Field(default_factory=list)
    permisos: list[str] = Field(default_factory=list)
    acotado: bool = False


# -- catálogo ----------------------------------------------------------------


class Norma(_Base):
    id: UUID
    norm_type: str
    norm_number: str | None = None
    title: str
    external_norm_id: str | None = None
    issuing_body: str | None = None
    status: str | None = None
    official_url: str | None = None
    subjects: list[Any] = Field(default_factory=list)
    updated_at: datetime
    # La normativa propia (RCA) vive en las mismas tablas con tenant_id no nulo (handoff §4).
    # El catálogo público no lo trae; si viniera con valor, no es catálogo público.
    tenant_id: UUID | None = None


class NormaPropia(_Base):
    """
    GET /compliance/normativa-propia/. No trae `updated_at`, y `articulos` es un conteo: el
    articulado se pide aparte en `/{id}/articulos`.
    """

    id: UUID
    tenant_id: UUID | None = None
    norm_type: str
    norm_number: str | None = None
    title: str
    issuing_body: str | None = None
    articulos: int = 0
    official_url: str | None = None


class VersionNorma(_Base):
    id: UUID
    norm_id: UUID | None = None
    valid_from: date | None = None
    valid_to: date | None = None  # null = todavía rige
    is_current: bool = False
    content_hash: str | None = None


class Articulo(_Base):
    id: UUID
    norm_version_id: UUID
    parent_article_id: UUID | None = None
    external_article_id: str | None = None
    article_type: str
    article_number: str | None = None
    heading: str | None = None
    content: str | None = None
    display_order: int = 0
    effective_from: date | None = None
    effective_to: date | None = None
    updated_at: datetime | None = None


# -- empresa -----------------------------------------------------------------


class Instalacion(_Base):
    """GET /facilities/. `environmental_identifiers` guarda ids sectoriales ({"rca", "seia_id"} en la semilla)."""

    id: UUID
    code: str
    name: str
    facility_type: str | None = None
    commune_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    environmental_identifiers: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class Obligacion(_Base):
    id: UUID
    code: str
    title: str
    status: str
    due_at: datetime | None = None
    period_start: date | None = None
    period_end: date | None = None
    owner_user_id: UUID | None = None
    updated_at: datetime | None = None


class Documento(_Base):
    id: UUID
    title: str
    document_type: str | None = None
    status: str | None = None
    current_version_id: UUID | None = None
    updated_at: datetime


class VersionDocumento(_Base):
    id: UUID
    document_id: UUID
    version_no: int
    file_name: str | None = None
    mime_type: str | None = None
    checksum_sha256: str | None = None
    # El ciclo de vida vive en la revisión (handoff §6). En el backend el campo es
    # `lifecycle_status` y arranca en "borrador" (models/documents.py).
    lifecycle_status: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None

    @property
    def estado_revision(self) -> str | None:
        return self.lifecycle_status


class EnlaceDescarga(_Base):
    url: str
    expires_in: int
    checksum_sha256: str | None = None


class Coincidencia(_Base):
    tipo: str
    id: UUID | str
    titulo: str
    codigo: str | None = None
    contexto: dict[str, Any] = Field(default_factory=dict)


class GrupoBusqueda(_Base):
    tipo: str
    hay_mas: bool = False
    coincidencias: list[Coincidencia] = Field(default_factory=list)


class ResultadoBusqueda(_Base):
    grupos: list[GrupoBusqueda] = Field(default_factory=list)


class Historial(_Base):
    eventos: list[dict[str, Any]] = Field(default_factory=list)
    fuentes: list[str] = Field(default_factory=list)
    fuentes_pendientes: list[str] = Field(default_factory=list)
    hay_mas: bool = False


class Comentario(_Base):
    id: UUID | int
    body: str | None = None
    cuerpo: str | None = None
    created_at: datetime | None = None

    @property
    def texto(self) -> str:
        return self.body or self.cuerpo or ""


# -- monitoreo: matriz legal, notificaciones, tickets --------------------------


class NormaDeMatriz(_Base):
    """GET /compliance/matrix-norms. Qué normas tiene una empresa en su matriz, y quién la sigue."""

    id: UUID
    matrix_id: UUID
    norm_id: UUID
    selected_version_id: UUID | None = None
    applicability: str | None = None
    owner_user_id: UUID | None = None


class Notificacion(_Base):
    id: UUID
    recipient_user_id: UUID | None = None
    channel: str
    subject: str | None = None
    status: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class NotificacionNueva(BaseModel):
    channel: str = "in_app"
    recipient_user_id: UUID | None = None
    subject: str
    body: str
    context: dict[str, Any] = Field(default_factory=dict)


class TicketNuevo(BaseModel):
    category: str = "legal"
    subject: str
    description: str
    priority: str = "medium"


class Ticket(_Base):
    id: UUID
    ticket_number: str | None = None
    subject: str
    status: str | None = None


class EmpresaDeCartera(_Base):
    """GET /tenants/ para el Admin Global: la cartera, sin datos de adentro de cada empresa."""

    id: UUID
    tenant_type: str
    legal_name: str
    trade_name: str | None = None
    status: str
    sector_id: int | None = None
    size_bracket: str | None = None
    created_at: datetime | None = None
    tiene_perfil_normativo: bool | None = None


# -- chatbot -----------------------------------------------------------------


class Conversacion(_Base):
    id: UUID
    tenant_id: UUID | None = None
    user_id: UUID
    title: str | None = None
    scope: str = "tenant"
    status: str | None = None


class Mensaje(_Base):
    id: int
    conversation_id: UUID
    role: str
    content: str
    citations: list[Any] = Field(default_factory=list)
    cited_norm_ids: list[UUID] = Field(default_factory=list)
    model_name: str | None = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class MensajeNuevo(BaseModel):
    role: str
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    cited_norm_ids: list[UUID] = Field(default_factory=list)
    model_name: str | None = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
