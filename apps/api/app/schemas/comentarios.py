"""Esquemas de la conversacion sobre un registro (RF-111, RF-112)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .base import OrmBase


class ComentarioCreate(BaseModel):
    entity_type: str
    entity_id: UUID
    body: str = Field(min_length=1, max_length=20_000)
    #: Nulo para un comentario raiz. El hilo es de **un solo nivel**: responder
    #: a una respuesta se rechaza diciendo cual es la raiz, en vez de
    #: reacomodarse solo — moverla cambia a quien le esta contestando el autor.
    parent_id: UUID | None = None
    #: **La lista la manda el cliente; el cuerpo es texto.** Deducir a quien se
    #: menciona buscando `@` en la cadena falla con nombres compuestos y con
    #: dos personas del mismo nombre, y falla **en silencio**: la notificacion
    #: simplemente no sale.
    menciones: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("body")
    @classmethod
    def no_solo_espacios(cls, v: str) -> str:
        # El CHECK de la base exige lo mismo. Comprobarlo aca da un 422 con
        # explicacion en vez de un 500 con un error de Postgres.
        if not v.strip():
            raise ValueError("El comentario no puede estar vacio.")
        return v


class ComentarioUpdate(BaseModel):
    """Solo el texto.

    `entity_type`, `entity_id`, `parent_id` y el autor no estan: son lo que el
    comentario **es**. Cambiarlos no lo edita — lo mueve de conversacion, o se
    lo atribuye a otra persona.
    """

    body: str = Field(min_length=1, max_length=20_000)

    @field_validator("body")
    @classmethod
    def no_solo_espacios(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El comentario no puede estar vacio.")
        return v


class ComentarioRead(OrmBase):
    id: UUID
    tenant_id: UUID
    entity_type: str
    entity_id: UUID
    author_user_id: UUID
    #: El nombre resuelto, para que la pantalla no tenga que pedir `/users/`
    #: y quedarse sin autor si esa llamada falla.
    author_name: str | None = None
    body: str
    parent_id: UUID | None
    #: Nulo si nunca se edito. **Se expone a proposito**: un comentario editado
    #: despues de que alguien lo respondio cambia lo que quedo escrito.
    edited_at: datetime | None
    menciones: list[UUID] = []
    created_at: datetime
