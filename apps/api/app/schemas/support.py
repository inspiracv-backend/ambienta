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


# ── La fachada del chatbot (RF-59 a RF-63) ──────────────────────────────────


class ConsultaDelChatbot(BaseModel):
    """Lo que el navegador manda para preguntar.

    **No lleva empresa ni usuario, y no es un olvido.** Los dos salen del token
    verificado. Un `tenant_id` en el cuerpo seria un parametro con el que
    cualquiera elige de que empresa leer, y la unica barrera pasaria a ser que
    el codigo no se equivoque.
    """

    pregunta: str = Field(
        min_length=2,
        max_length=2000,
        description=(
            "La pregunta en lenguaje natural. Los limites son los del contrato "
            "del AI Service: una de un caracter no es una pregunta, y una de "
            "miles no cabe en el contexto junto con la evidencia."
        ),
    )
    conversation_id: UUID | None = Field(
        default=None,
        description=(
            "La conversacion a la que pertenece el turno. **Si no viene, el AI "
            "Service la abre** y devuelve su id en la respuesta: el frontend lo "
            "guarda y lo manda en los turnos siguientes."
        ),
    )
    fecha: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description=(
            "Para preguntar por el texto legal **vigente a una fecha**, no al de "
            "hoy. Formato de calendario (`AAAA-MM-DD`) y no una marca de tiempo: "
            "la vigencia de una norma es un dia, no un instante."
        ),
    )


class RespuestaDelChatbot(BaseModel):
    """La respuesta del AI Service, retransmitida.

    **Acepta campos que no declara** (`extra="allow"`). El contrato lo escribe y
    lo versiona el AI Service, no esta API: con un modelo cerrado, cada campo que
    ellos agreguen se perderia en silencio al pasar por la fachada — y "la API
    se come un dato" es exactamente el defecto que este repositorio ya sufrio
    con `attributes` y con el ciclo de vida documental.

    Se declaran los cinco obligatorios del contrato para que Swagger diga algo
    util y para que un cambio incompatible falle aca y no en la pantalla.
    """

    model_config = ConfigDict(extra="allow")

    conversation_id: UUID | None = Field(
        description="La conversacion, abierta por el AI Service si no se mando una."
    )
    respuesta: str = Field(description="El texto fundamentado.")
    se_abstuvo: bool = Field(
        description=(
            "**Campo propio, no se deduce del texto.** El frontend muestra "
            "distinto una respuesta con evidencia y un «no tengo informacion "
            "suficiente», y adivinarlo leyendo la respuesta es como se termina "
            "presentando una abstencion como un hecho."
        )
    )
    citas: list = Field(description="De donde sale cada afirmacion.")
    guardado: bool = Field(
        description=(
            "Si el turno quedo en la conversacion. En modo desarrollo no hay "
            "usuario, asi que no se guarda y esto viene en `false`."
        )
    )
