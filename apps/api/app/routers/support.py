from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.support import crud_chatbot_conversation, crud_chatbot_message, crud_support_ticket, crud_ticket_message
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.support import (
    ChatbotConversationCreate,
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
def list_tickets(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_support_ticket.get_multi(db, skip=skip, limit=limit)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketRead)
def get_ticket(ticket_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_support_ticket.get(db, ticket_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return obj


@router.post("/tickets", response_model=SupportTicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: SupportTicketCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_support_ticket.create(db, obj_in=data, tenant_id=tenant_id)
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
def list_conversations(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_chatbot_conversation.get_multi(db, skip=skip, limit=limit)


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
