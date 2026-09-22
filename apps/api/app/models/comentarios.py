"""La conversacion sobre un registro (RF-111 y RF-112, #74).

Ver `db/28_comentarios.sql` para el por que de cada decision. Lo que conviene
saber leyendo esto:

- `entity_type` + `entity_id` es **polimorfico y sin clave foranea**, igual que
  `entity_documents`, y lo comprueba el mismo mapa:
  `services/vinculos_de_documentos.py::ANCLAJES`.
- `author_user_id` es **obligatorio**. Sin sesion identificada el endpoint
  responde 409 en vez de atribuirle el comentario a alguien.
- El hilo es de **un solo nivel**, y eso lo exige el servicio: Postgres no
  puede mirar la fila del padre desde un CHECK.
"""
from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class Comment(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "comments"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comments.id")
    )
    #: Nulo hasta la primera edicion. **Se expone**: un comentario editado
    #: despues de que alguien lo respondio cambia lo que quedo escrito.
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommentMention(Base, TenantMixin):
    __tablename__ = "comment_mentions"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uq_comment_mentions"),)

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    comment_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
