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
    #: **El codigo es lo que se cita en una auditoria.** Existe en la tabla
    #: desde `db/18` y este esquema no lo exponia, asi que ninguna pantalla
    #: podia mostrarlo: un documento controlado sin codigo visible no se puede
    #: referenciar, que es la mitad de para que sirve controlarlo.
    code: str | None = None
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
    # ── Ciclo de vida (db/18, RF-104 a RF-106) ────────────────────────────
    #
    # Estas siete columnas existian en la tabla y **no salian por la API**, asi
    # que el control documental era invisible desde fuera: no habia forma de
    # saber si una revision era un borrador o la que rige. Sin esto, la
    # pantalla no puede distinguir lo que sirve como evidencia de lo que no.
    lifecycle_status: str
    approved_at: datetime | None = None
    approved_by: UUID | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    obsoleted_at: datetime | None = None
    obsoleted_reason: str | None = None


# ── EntityDocument ────────────────────────────────────────────────────────

# ── Subida de archivos (RF-110) ───────────────────────────────────────────

class PedirSubida(BaseModel):
    """Lo que la pantalla declara antes de subir.

    Es **lo declarado, no lo real**: con enlaces firmados el archivo va directo
    al bucket sin pasar por nosotros. Sirve para cortar el caso normal —un
    `.exe`, un archivo de 800 MB— antes de gastar la subida; lo que llego de
    verdad se comprueba despues con `confirmar`.
    """

    file_name: str
    mime_type: str
    size_bytes: int
    #: SHA-256 del contenido, en hexadecimal. **Opcional a proposito.**
    #:
    #: Cuando viene, viaja **dentro de la firma** y el bucket comprueba el
    #: contenido: si no corresponde rechaza la subida y no queda nada escrito.
    #: Eso es un hash **verificado**; guardar el que declara el navegador seria
    #: uno **afirmado**, que sirve contra la corrupcion en el trayecto y no
    #: sirve para nada si quien sube miente.
    #:
    #: Sin el, la subida funciona igual y la revision queda sin checksum — que
    #: es preferible a guardar un valor que nadie comprobo. Es opcional porque
    #: calcularlo obliga al navegador a leer el archivo entero.
    checksum_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 del contenido en hexadecimal (64 caracteres).",
    )


class EnlaceDeSubida(BaseModel):
    """El permiso temporal, y todo lo que el navegador necesita para usarlo."""

    url: str
    #: Se devuelve para que la pantalla la mande de vuelta al confirmar.
    storage_key: str
    expires_in: int
    #: **Hay que mandarlas tal cual.** Van dentro de la firma: con otras, B2
    #: rechaza la subida.
    headers: dict[str, str]


class ConfirmarSubida(BaseModel):
    """Cierra la subida creando la revision, con los datos **reales** del objeto."""

    storage_key: str
    file_name: str


class PuestaEnVigencia(BaseModel):
    """Desde cuando rige, y por que se retira la anterior.

    Las dos opcionales: lo normal es "desde hoy" y sin explicacion. El motivo
    viaja aca y no en una llamada aparte porque **retirar la anterior pasa en el
    mismo paso** —lo exige la restriccion de una sola revision vigente— y
    pedirlo despues dejaria la obsolescencia sin explicar si alguien no vuelve.
    """

    desde: date | None = None
    motivo: str | None = None


class MotivoDeObsolescencia(BaseModel):
    """Obligatorio, y por eso es un esquema y no un parametro opcional."""

    motivo: str


class EnlaceDeDescarga(BaseModel):
    url: str
    expires_in: int


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


class DocumentVersionUpdate(BaseModel):
    """Metadatos de una version. El archivo en si no se reemplaza: subir otro
    contenido es otra version, y por eso existe el versionado."""

    change_note: str | None = None
    checksum: str | None = None
