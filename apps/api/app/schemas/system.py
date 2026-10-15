from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .base import OrmBase


# ── IntegrationAccount ────────────────────────────────────────────────────

class IntegrationAccountCreate(BaseModel):
    provider: str
    external_account_id: str | None = None
    display_name: str | None = None
    scopes: list[str] = Field(default_factory=list)
    secret_reference: str | None = None


class IntegrationAccountRead(OrmBase):
    id: UUID
    tenant_id: UUID
    provider: str
    external_account_id: str | None
    display_name: str | None
    status: str
    scopes: list[str]
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ── AuditLog ──────────────────────────────────────────────────────────────

class AuditLogCreate(BaseModel):
    actor_user_id: UUID | None = None
    action: str
    entity_type: str
    entity_id: UUID | None = None
    request_id: UUID | None = None
    ip_address: str | None = None
    reason: str | None = None
    before_data: dict | None = None
    after_data: dict | None = None
    metadata: dict = Field(default_factory=dict)


class AuditLogRead(OrmBase):
    id: int
    tenant_id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    request_id: UUID | None
    ip_address: str | None
    reason: str | None
    before_data: dict | None
    after_data: dict | None
    #: Quien actuo, por nombre. `None` sin actor —un proceso, o el modo de
    #: desarrollo— o si la persona es de otra empresa (un gestor): RLS no la deja
    #: ver, y eso no se disfraza.
    actor_nombre: str | None = None


class IntegrationAccountUpdate(BaseModel):
    """Lo editable de una cuenta de integracion.

    `provider` no esta: cambiar el proveedor de una cuenta existente no es una
    edicion, es otra cuenta — y dejaria `external_account_id`, `scopes` y el
    secreto apuntando a un sistema que ya no es el suyo.

    `secret_reference` si se puede cambiar, porque rotar credenciales es
    operacion normal. Nunca sale en la lectura: `IntegrationAccountRead` no lo
    incluye, y asi debe seguir.
    """

    external_account_id: str | None = None
    display_name: str | None = None
    status: str | None = None
    scopes: list[str] | None = None
    secret_reference: str | None = None


# ── El estado de los agentes de IA (RF-61, RF-62) ───────────────────────────


class CorridaDeAgente(BaseModel):
    """Una ejecucion de un trabajo de fondo del AI Service.

    `model_config` con `extra="allow"` por el mismo motivo que la respuesta del
    chatbot: **el contrato lo versiona el AI Service**, y un modelo cerrado se
    come en silencio cada campo que ellos agreguen.
    """

    model_config = ConfigDict(extra="allow")

    nombre: str
    estado: str = Field(description="`ejecutando`, `ok` o `error`.")
    iniciado_en: datetime | None = None
    finalizado_en: datetime | None = None
    elementos: int = Field(description="Cuantos elementos proceso la corrida.")
    detalle: str | None = None


class EstadoDeLosAgentesIA(BaseModel):
    """Lo que el panel de plataforma necesita para saber si la IA esta al dia.

    **Un trabajo que fallo en silencio es el peor estado posible** en este
    producto: la ingesta no indexa, el chatbot responde "no tengo informacion
    suficiente" y nada dice que la causa es un cron caido de hace dos semanas.
    """

    model_config = ConfigDict(extra="allow")

    agentes: list[CorridaDeAgente]
