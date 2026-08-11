from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase


# ── Document ──────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    document_type: str
    title: str
    classification: str = "internal"
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class DocumentRead(OrmBase):
    id: UUID
    tenant_id: UUID
    document_type: str
    current_version_id: UUID | None
    title: str
    classification: str
    status: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = None
    classification: str | None = None
    status: str | None = None
    tags: list[str] | None = None


# ── DocumentVersion ───────────────────────────────────────────────────────

class DocumentVersionCreate(BaseModel):
    document_id: UUID
    version_no: int
    storage_provider: str
    storage_key: str
    file_name: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str | None = None
    source: str = "upload"
    version_metadata: dict = Field(default_factory=dict)


class DocumentVersionRead(OrmBase):
    id: UUID
    tenant_id: UUID
    document_id: UUID
    version_no: int
    storage_provider: str
    storage_key: str
    file_name: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str | None
    source: str
    version_metadata: dict
    created_at: datetime
    created_by: UUID | None


# ── EntityDocument ────────────────────────────────────────────────────────

class EntityDocumentCreate(BaseModel):
    document_id: UUID
    entity_type: str
    entity_id: UUID
    purpose: str
    is_required: bool = False
    valid_from: date | None = None
    valid_to: date | None = None


class EntityDocumentRead(OrmBase):
    id: int
    tenant_id: UUID
    document_id: UUID
    entity_type: str
    entity_id: UUID
    purpose: str
    is_required: bool
    valid_from: date | None
    valid_to: date | None
    created_at: datetime
    updated_at: datetime


class EntityDocumentUpdate(BaseModel):
    """Lo editable de un vinculo documento-entidad.

    `document_id`, `entity_type` y `entity_id` no estan: son lo que el vinculo
    **es**. Cambiarlos no lo edita, lo convierte en otro vinculo — y dejaria la
    ruta anidada mintiendo sobre a que documento pertenece.
    """

    purpose: str | None = None
    is_required: bool | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class EntityDocumentCreateAnidado(BaseModel):
    """Cuerpo de `POST /documents/{document_id}/entities`.

    `document_id` viene del path. `entity_type` y `entity_id` se quedan: son
    el destino del vinculo, no el origen.
    """

    entity_type: str
    entity_id: UUID
    purpose: str
    is_required: bool = False
    valid_from: date | None = None
    valid_to: date | None = None
