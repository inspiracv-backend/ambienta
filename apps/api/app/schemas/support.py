from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .base import OrmBase


# ── SupportTicket ─────────────────────────────────────────────────────────

class SupportTicketCreate(BaseModel):
    created_by_user_id: UUID | None = None
    guest_name: str | None = None
    guest_email: str | None = None
    category: str
    subject: str
    description: str
    priority: str = "medium"


class SupportTicketRead(OrmBase):
    id: UUID
    tenant_id: UUID
    ticket_number: str
    created_by_user_id: UUID | None
    guest_name: str | None
    guest_email: str | None
    category: str
    subject: str
    description: str
    priority: str
    status: str
    assigned_to: UUID | None
    related_entity_type: str | None
    related_entity_id: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SupportTicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to: UUID | None = None


# ── SupportTicketMessage ──────────────────────────────────────────────────

class SupportTicketMessageCreate(BaseModel):
    ticket_id: UUID
    author_user_id: UUID | None = None
    author_guest_email: str | None = None
    message_type: str = "comment"
    body: str
    is_internal: bool = False


class SupportTicketMessageRead(OrmBase):
    id: int
    tenant_id: UUID
    ticket_id: UUID
    author_user_id: UUID | None
    author_guest_email: str | None
    message_type: str
    body: str
    is_internal: bool
    created_at: datetime


# ── ChatbotConversation ───────────────────────────────────────────────────

class ChatbotConversationCreate(BaseModel):
    user_id: UUID
    title: str | None = None
    scope: str = "tenant"
    facility_id: UUID | None = None


class ChatbotConversationRead(OrmBase):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    title: str | None
    scope: str
    facility_id: UUID | None
    status: str
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ── ChatbotMessage ────────────────────────────────────────────────────────

class ChatbotMessageCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    conversation_id: UUID
    role: str
    content: str
    model_name: str | None = None
    token_usage: dict = Field(default_factory=dict)


class ChatbotMessageRead(OrmBase):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    tenant_id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: list
    model_name: str | None
    token_usage: dict
    feedback: dict
    created_at: datetime


class SupportTicketMessageUpdate(BaseModel):
    """Correccion del texto de un mensaje. `ticket_id` y el autor no cambian:
    editar quien dijo algo seria falsificar la conversacion."""

    body: str | None = None
    is_internal: bool | None = None


class ChatbotConversationUpdate(BaseModel):
    """Estado y titulo de una conversacion."""

    title: str | None = None
    status: str | None = None


class ChatbotMessageUpdate(BaseModel):
    """Solo las citas: el contenido del mensaje es lo que se dijo."""

    citations: dict | None = None
