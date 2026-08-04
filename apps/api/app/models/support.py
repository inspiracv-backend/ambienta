from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class SupportTicket(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint(
            "created_by_user_id IS NOT NULL OR guest_email IS NOT NULL",
            name="ck_support_tickets_autor",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ticket_number: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False
    )
    created_by_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    guest_name: Mapped[str | None] = mapped_column(String(180))
    guest_email: Mapped[str | None] = mapped_column(CITEXT)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="medium"
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="open"
    )
    assigned_to: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    related_entity_type: Mapped[str | None] = mapped_column(String(40))
    related_entity_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages = relationship(
        "SupportTicketMessage", back_populates="ticket", lazy="select"
    )


class SupportTicketMessage(Base, TenantMixin):
    __tablename__ = "support_ticket_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    author_guest_email: Mapped[str | None] = mapped_column(CITEXT)
    message_type: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="comment"
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket = relationship("SupportTicket", back_populates="messages", lazy="select")


class ChatbotConversation(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "chatbot_conversations"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(240))
    scope: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="tenant"
    )
    facility_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    context_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages = relationship(
        "ChatbotMessage", back_populates="conversation", lazy="select"
    )


class ChatbotMessage(Base, TenantMixin):
    __tablename__ = "chatbot_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatbot_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cited_norm_ids: Mapped[list] = mapped_column(
        "cited_norm_ids", JSONB, nullable=False, server_default="[]"
    )
    citations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    model_name: Mapped[str | None] = mapped_column(String(100))
    token_usage: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    feedback: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation = relationship(
        "ChatbotConversation", back_populates="messages", lazy="select"
    )
