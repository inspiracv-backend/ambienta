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
    """Un mensaje de la conversacion con el asistente.

    ## Las citas se declaran aca, y hasta el 8-sep no estaban

    `chatbot_messages` tiene `citations` y `cited_norm_ids` desde el principio,
    y **este esquema no las declaraba**: Pydantic descarta en silencio lo que no
    declara, asi que el AI Service podia mandar sus citas, recibir **201**, y la
    fila quedaba con `[]`. Sin ningun error.

    Es el mismo defecto que este repositorio ya sufrio con `planned_start_date`
    y con `process_id`, y aca pega en lo que el asistente existe para dar: una
    respuesta **con de donde la saco**. Una respuesta normativa sin cita no se
    puede verificar, y en cumplimiento eso es todo lo que importa.
    """

    model_config = ConfigDict(protected_namespaces=())

    conversation_id: UUID
    role: str
    content: str
    #: De donde salio la respuesta. Forma libre —cada motor cita distinto— pero
    #: **es una lista**, igual que la columna y que la lectura.
    citations: list = Field(default_factory=list)
    #: Los identificadores de las normas citadas, aparte del texto de la cita.
    #: Sirve para responder "que normas menciono el asistente" sin parsear.
    cited_norm_ids: list = Field(default_factory=list)
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
    #: Estaba en la tabla y **no salia en ninguna respuesta**: se podia escribir
    #: y no leer. Es el detector de "columnas que ninguna respuesta expone",
    #: aplicado al dato que sostiene una respuesta normativa.
    cited_norm_ids: list = []
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
    """Solo las citas: el contenido del mensaje es lo que se dijo.

    **`list` y no `dict`.** Decia `dict | None` mientras la columna es JSONB con
    `[]` por defecto y `ChatbotMessageRead` la declara `list`: un PATCH con un
    diccionario se escribia y despues la lectura no validaba contra su propio
    contrato. Dos esquemas del mismo campo diciendo tipos distintos.
    """

    citations: list | None = None
    cited_norm_ids: list | None = None
