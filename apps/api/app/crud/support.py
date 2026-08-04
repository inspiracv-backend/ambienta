from pydantic import BaseModel

from ..models.support import ChatbotConversation, ChatbotMessage, SupportTicket, SupportTicketMessage
from ..schemas.support import (
    ChatbotConversationCreate,
    ChatbotMessageCreate,
    SupportTicketCreate,
    SupportTicketMessageCreate,
    SupportTicketUpdate,
)
from .base import CRUDBase

crud_support_ticket = CRUDBase[SupportTicket, SupportTicketCreate, SupportTicketUpdate](SupportTicket)
crud_ticket_message = CRUDBase[SupportTicketMessage, SupportTicketMessageCreate, BaseModel](SupportTicketMessage)
crud_chatbot_conversation = CRUDBase[ChatbotConversation, ChatbotConversationCreate, BaseModel](ChatbotConversation)
crud_chatbot_message = CRUDBase[ChatbotMessage, ChatbotMessageCreate, BaseModel](ChatbotMessage)
