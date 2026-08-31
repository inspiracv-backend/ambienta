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
from ._comun import borrar_o_404, obtener_o_404, verificar_padre
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


@router.get("/tickets/{ticket_id}/messages", response_model=list[SupportTicketMessageRead])
def list_ticket_messages(ticket_id: UUID, db: Session = Depends(get_tenant_db)):
    from sqlalchemy import select
    from ..models.support import SupportTicketMessage
    stmt = select(SupportTicketMessage).where(SupportTicketMessage.ticket_id == ticket_id)
    return list(db.scalars(stmt).all())


@router.post("/tickets/{ticket_id}/messages", response_model=SupportTicketMessageRead, status_code=status.HTTP_201_CREATED)
def create_ticket_message(
    ticket_id: UUID,
    data: SupportTicketMessageCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..models.support import SupportTicketMessage
    msg_data = data.model_dump(exclude_unset=True)
    msg_data["ticket_id"] = ticket_id
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


@router.get("/chatbot/{conversation_id}/messages", response_model=list[ChatbotMessageRead])
def list_chatbot_messages(conversation_id: UUID, db: Session = Depends(get_tenant_db)):
    from sqlalchemy import select
    from ..models.support import ChatbotMessage
    stmt = select(ChatbotMessage).where(ChatbotMessage.conversation_id == conversation_id)
    return list(db.scalars(stmt).all())


@router.post("/chatbot/{conversation_id}/messages", response_model=ChatbotMessageRead, status_code=status.HTTP_201_CREATED)
def create_chatbot_message(
    conversation_id: UUID,
    data: ChatbotMessageCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..models.support import ChatbotMessage
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
    falsificar la conversacion con el cliente."""
    obj = obtener_o_404(crud_ticket_message, db, mensaje_id, recurso="SupportTicketMessage")
    verificar_padre(obj, ticket_id, campo="ticket_id")
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



