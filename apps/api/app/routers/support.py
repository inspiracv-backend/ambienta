from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..models.organization import User
from ..crud.support import (
    crud_chatbot_conversation,
    crud_chatbot_message,
    crud_support_ticket,
    crud_ticket_message,
)
from ..deps import get_current_user, get_tenant_db, get_tenant_id
from ._paginacion import Pagina, paginacion, recortar
from ._comun import borrar_o_404, obtener_o_404, validar_visible, verificar_padre
from ..crud.organization import crud_user
from ..schemas.support import (
    ChatbotConversationCreate,
    ChatbotConversationUpdate,
    ChatbotMessageUpdate,
    SupportTicketMessageUpdate,
    ChatbotConversationRead,
    ChatbotMessageCreate,
    ChatbotMessageRead,
    SupportTicketCreate,
    SupportTicketMessageCreate,
    SupportTicketMessageRead,
    SupportTicketRead,
    SupportTicketUpdate,
)

router = APIRouter(prefix="/support", tags=["support"])


@router.get("/tickets", response_model=list[SupportTicketRead])
def list_tickets(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_support_ticket.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketRead)
def get_ticket(ticket_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_support_ticket.get(db, ticket_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return obj


@router.post("/tickets", response_model=SupportTicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: SupportTicketCreate,
    user: CurrentUser = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Crea una solicitud de soporte.

    El numero de ticket lo pone la base (secuencia), no el cliente.

    **El autor tampoco lo elige quien llama.** Sale de la sesion: si el
    esquema aceptara `created_by_user_id` del cuerpo, cualquiera podria
    atribuirle una solicitud a otra persona. El campo existe en el esquema por
    compatibilidad, pero se ignora.

    La base exige autor —`created_by_user_id` o `guest_email`, por CHECK—
    porque un ticket sin quien lo pide no se puede responder. Si la sesion no
    identifica a nadie, que es lo que pasa con el fallback de desarrollo y con
    el Cliente Invitado, hace falta el correo de contacto.
    """
    autor = db.scalar(select(User).where(User.clerk_id == user.user_id)) if user.user_id else None

    datos = data.model_copy(update={"created_by_user_id": autor.id if autor else None})
    if autor is None and not datos.guest_email:
        # Se distinguen dos causas porque piden cosas distintas. Decirle
        # "inicia sesion" a alguien que ya la inicio manda a buscar el problema
        # donde no esta.
        if user.user_id:
            detalle = (
                "La sesion es valida pero ese usuario no esta vinculado a "
                "ninguna persona de la empresa. Ocurre cuando el webhook de "
                "alta no llego a procesarse: falta `clerk_id` en la fila."
            )
        else:
            detalle = (
                "Un ticket necesita autor: iniciar sesion, o indicar "
                "guest_email para el seguimiento."
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detalle
        )

    obj = crud_support_ticket.create(db, obj_in=datos, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/tickets/{ticket_id}", response_model=SupportTicketRead)
def update_ticket(ticket_id: UUID, data: SupportTicketUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_support_ticket.get(db, ticket_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    obj = crud_support_ticket.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get(
    "/tickets/{ticket_id}/messages",
    response_model=list[SupportTicketMessageRead],
    summary="La conversacion de un ticket, en orden",
)
def list_ticket_messages(ticket_id: UUID, db: Session = Depends(get_tenant_db)):
    """El hilo del ticket, del mas antiguo al mas nuevo.

    **Tenia los dos defectos que el 8-sep se arreglaron en los mensajes del
    chatbot**, y nadie los habia mirado aca: sin `ORDER BY` —Postgres devuelve
    el orden fisico, y un `UPDATE` que no puede ser HOT mueve la fila al
    final— y sin comprobar el ticket, asi que uno inexistente respondia `[]`,
    que se lee como "este ticket no tiene mensajes".

    Importa mas desde el 13-sep: **las correcciones de un registro erroneo
    (RF-83) viven aca**, como `internal_note`. Un historial de correcciones
    barajado le cambia el sentido a lo que se corrigio.
    """
    from sqlalchemy import select

    from ..models.support import SupportTicketMessage

    obtener_o_404(crud_support_ticket, db, ticket_id, recurso="SupportTicket")
    stmt = (
        select(SupportTicketMessage)
        .where(SupportTicketMessage.ticket_id == ticket_id)
        .order_by(SupportTicketMessage.created_at, SupportTicketMessage.id)
    )
    return list(db.scalars(stmt).all())


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=SupportTicketMessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar un mensaje o una correccion al ticket",
)
def create_ticket_message(
    ticket_id: UUID,
    data: SupportTicketMessageCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    actual: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """Escribe un turno del hilo.

    ## El autor sale de la sesion, no del cuerpo

    `author_user_id` venia **del cuerpo, sin mirarlo**. Para un comentario
    cualquiera es un descuido; para una **correccion de un registro erroneo**
    (RF-83) es lo que invalida el requisito entero: la pantalla promete *"queda
    registrado con tu nombre"*, y ese nombre lo elegia quien mandaba la
    peticion. Una correccion atribuida a otro es exactamente lo que un auditor
    no puede distinguir de una real.

    Cuando hay sesion identificada, **gana el usuario de la sesion** y lo que
    diga el cuerpo se ignora. Sin sesion —el modo `X-Tenant-Id` de desarrollo—
    el id del cuerpo se acepta solo si es de esta empresa: **las claves foraneas
    no pasan por RLS** (CLAUDE.md §4), asi que sin esa comprobacion se podia
    firmar con el id de alguien de otra empresa.

    ## Y el ticket se comprueba antes de escribir

    Mismo arreglo que los mensajes del chatbot:

    | lo que se manda | antes | ahora |
    |---|---|---|
    | un ticket inexistente | **500** — revienta la clave foranea | 404 |
    | el ticket de otra empresa | **201**, y la fila quedaba escrita | 404 |
    """
    from sqlalchemy import select

    from ..models.support import SupportTicketMessage

    obtener_o_404(crud_support_ticket, db, ticket_id, recurso="SupportTicket")

    msg_data = data.model_dump(exclude_unset=True)
    msg_data["ticket_id"] = ticket_id

    autor = None
    if actual is not None and actual.user_id:
        autor = db.scalars(
            select(User).where(User.clerk_id == actual.user_id, User.deleted_at.is_(None))
        ).first()
    if autor is not None:
        msg_data["author_user_id"] = autor.id
    else:
        validar_visible(
            crud_user, db, msg_data.get("author_user_id"), campo="author_user_id"
        )

    obj = SupportTicketMessage(**msg_data, tenant_id=tenant_id)
    db.add(obj)
    db.flush()
    db.refresh(obj)
    db.commit()
    return obj


@router.get("/chatbot", response_model=list[ChatbotConversationRead])
def list_conversations(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_chatbot_conversation.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.post("/chatbot", response_model=ChatbotConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    data: ChatbotConversationCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_chatbot_conversation.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.get(
    "/chatbot/{conversation_id}/messages",
    response_model=list[ChatbotMessageRead],
    summary="Los mensajes de una conversacion, en orden",
)
def list_chatbot_messages(conversation_id: UUID, db: Session = Depends(get_tenant_db)):
    """El hilo completo, del mas antiguo al mas nuevo.

    ## El `ORDER BY` no es cosmetico: en un chat el orden ES la conversacion

    Esta consulta no tenia ninguno. Sin `ORDER BY`, Postgres devuelve las filas
    como quiera —en la practica, el orden fisico del heap— y **un `UPDATE`
    mueve la fila al final**. O sea que el `PATCH` que existe justamente para
    agregarle las citas a un mensaje lo mandaba al final del hilo: la respuesta
    quedaba despues de la pregunta que vino tres turnos mas tarde.

    Para el servicio de IA eso no es un detalle de presentacion. De aca sale el
    contexto que se le manda al modelo, y un historial barajado le hace
    contestar otra cosa — sin ningun error a la vista. Es el mismo defecto que
    ya estaba documentado en `/catalog/norms` ("sin `ORDER BY` la paginacion se
    rompe en silencio"), aca sobre el dato que da sentido al modulo.

    Se desempata por `id` —`BIGSERIAL`, o sea orden de insercion— porque dos
    mensajes escritos en la misma transaccion comparten `created_at`. Misma
    leccion que los usuarios del seed.

    Y una conversacion que no existe responde **404**, no una lista vacia: para
    quien indexa, `[]` se lee como "esta conversacion no tiene mensajes", que es
    una afirmacion distinta.
    """
    from sqlalchemy import select

    from ..models.support import ChatbotMessage

    obtener_o_404(
        crud_chatbot_conversation, db, conversation_id, recurso="ChatbotConversation"
    )
    stmt = (
        select(ChatbotMessage)
        .where(ChatbotMessage.conversation_id == conversation_id)
        .order_by(ChatbotMessage.created_at, ChatbotMessage.id)
    )
    return list(db.scalars(stmt).all())


@router.post(
    "/chatbot/{conversation_id}/messages",
    response_model=ChatbotMessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar un mensaje de la conversacion",
)
def create_chatbot_message(
    conversation_id: UUID,
    data: ChatbotMessageCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Escribe un turno del hilo, con sus citas si las tiene.

    **La conversacion se comprueba antes de escribir**, y era el unico endpoint
    anidado de este router que no lo hacia. Sin eso pasaban dos cosas, ninguna
    con el codigo correcto:

    | lo que se manda | antes | ahora |
    |---|---|---|
    | una conversacion inexistente | **500** — revienta la clave foranea | 404 |
    | la conversacion de otra empresa | **201**, y la fila quedaba escrita | 404 |

    El segundo es el conocido: **las claves foraneas no pasan por RLS**
    (CLAUDE.md §4), asi que la restriccion solo exige que la fila exista, no que
    sea de esta empresa. El mensaje quedaba con el `tenant_id` propio colgando
    de un hilo ajeno — invisible para las dos empresas y contando en los
    conteos de una.

    El 500 es el que mas duele en una integracion: un servicio que reintenta
    ante un 5xx reintenta para siempre algo que nunca va a funcionar.

    `conversation_id` sale de la **ruta**, no del cuerpo. El esquema tambien lo
    declara —lo pide el contrato— pero si los dos discrepan manda la URL: es
    donde el recurso ya se comprobo.
    """
    from ..models.support import ChatbotMessage

    obtener_o_404(
        crud_chatbot_conversation, db, conversation_id, recurso="ChatbotConversation"
    )

    msg_data = data.model_dump(exclude_unset=True)
    msg_data["conversation_id"] = conversation_id
    obj = ChatbotMessage(**msg_data, tenant_id=tenant_id)
    db.add(obj)
    db.flush()
    db.refresh(obj)
    db.commit()
    return obj


@router.delete("/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira un ticket. Sus mensajes no se exponen para borrado: son la
    conversacion con el cliente y borrar uno suelto la volveria enganosa."""
    borrar_o_404(crud_support_ticket, db, ticket_id, recurso="SupportTicket")


@router.get("/chatbot/{conversation_id}", response_model=ChatbotConversationRead)
def get_chatbot_conversation(conversation_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_chatbot_conversation, db, conversation_id, recurso="ChatbotConversation")


@router.patch("/chatbot/{conversation_id}", response_model=ChatbotConversationRead)
def update_conversation(conversation_id: UUID, data: ChatbotConversationUpdate, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_chatbot_conversation, db, conversation_id, recurso="ChatbotConversation")
    obj = crud_chatbot_conversation.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/chatbot/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_chatbot_conversation, db, conversation_id, recurso="ChatbotConversation")


@router.get("/tickets/{ticket_id}/messages/{mensaje_id}", response_model=SupportTicketMessageRead)
def get_ticket_message(ticket_id: UUID, mensaje_id: int, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_ticket_message, db, mensaje_id, recurso="SupportTicketMessage")
    return verificar_padre(obj, ticket_id, campo="ticket_id")


@router.patch("/tickets/{ticket_id}/messages/{mensaje_id}", response_model=SupportTicketMessageRead)
def update_ticket_message(ticket_id: UUID, mensaje_id: int, data: SupportTicketMessageUpdate, db: Session = Depends(get_tenant_db)):
    """Corrige el texto. El autor no cambia: editar quien dijo algo seria
    falsificar la conversacion con el cliente.

    **Una `internal_note` no se edita.** Desde el 13-sep las correcciones de un
    registro erroneo (RF-83) viven ahi, y la pantalla promete que "no se puede
    editar despues". La tabla no tiene `updated_at`: una correccion reescrita
    no deja rastro de que lo fue. Si la correccion estaba mal, se agrega otra.
    """
    obj = obtener_o_404(crud_ticket_message, db, mensaje_id, recurso="SupportTicketMessage")
    verificar_padre(obj, ticket_id, campo="ticket_id")
    if obj.message_type == "internal_note":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Una correccion registrada no se edita. Si estaba mal, "
                "registra otra que la corrija."
            ),
        )
    obj = crud_ticket_message.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# Los mensajes NO se borran, ni siquiera de forma logica.
#
# Un hilo de soporte es el registro de lo que se le dijo a un cliente. Quitarle
# un mensaje suelto no deja el hilo mas corto: lo deja **enganoso**, porque las
# respuestas que vienen despues siguen contestando algo que ya no aparece.
#
# El borrado existio y se retiro el 13-ago-2026: se habia expuesto aplicando
# "DELETE en todos los routers" de forma uniforme, sin releer que este caso
# estaba excluido a proposito (docs/estado-crud-base-de-datos.md).
#
# Corregir un mensaje se hace con PATCH, que deja el hilo completo y coherente.


@router.get("/chatbot/{conversation_id}/messages/{mensaje_id}", response_model=ChatbotMessageRead)
def get_chatbot_message(conversation_id: UUID, mensaje_id: int, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_chatbot_message, db, mensaje_id, recurso="ChatbotMessage")
    return verificar_padre(obj, conversation_id, campo="conversation_id")


@router.patch("/chatbot/{conversation_id}/messages/{mensaje_id}", response_model=ChatbotMessageRead)
def update_chatbot_message(conversation_id: UUID, mensaje_id: int, data: ChatbotMessageUpdate, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_chatbot_message, db, mensaje_id, recurso="ChatbotMessage")
    verificar_padre(obj, conversation_id, campo="conversation_id")
    obj = crud_chatbot_message.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj



