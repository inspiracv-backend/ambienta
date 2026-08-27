from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class NotificationTemplate(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_notification_templates"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    locale: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default="es-CL"
    )
    subject_template: Mapped[str | None] = mapped_column(String(400))
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    version_no: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class NotificationRule(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "notification_rules"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    lead_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    recipient_rule: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    template_code: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Notification(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "notifications"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    rule_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notification_rules.id")
    )
    recipient_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="queued"
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    # Identifica QUE aviso es, para no repetirlo (db/17). Detras hay un indice
    # unico parcial: `(tenant_id, dedupe_key)` donde no este borrado ni sea
    # NULL. NULL = un aviso que puede repetirse legitimamente.
    dedupe_key: Mapped[str | None] = mapped_column(String(200))
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
