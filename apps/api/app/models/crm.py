"""CRM simplificado: empresas, contactos, pipeline y actividades (epica #32).

Espejo de `db/22_crm.sql`. Lo que conviene saber al leerlo:

**`crm_companies` no es `tenants` ni es `contracts`.** `contracts` une dos
tenants, o sea que solo cabe quien **ya es cliente de la plataforma**. Una
empresa a la que todavia se le esta vendiendo no tenia donde vivir, y por eso
el seguimiento comercial pasaba fuera del sistema.
`crm_companies.client_tenant_id` es el puente: nulo mientras es prospecto, y
cuando entra a la plataforma permite promover el trato ganado a `contracts`.

**Las etapas son una tabla.** #78 las pide configurables por empresa, y `kind`
separa como la llama la empresa de que significa para el sistema.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID as PyUUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class CrmStage(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "crm_stages"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: El orden en el kanban. Se reordena a mano, por eso no es una secuencia.
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    #: `open` | `won` | `lost`. **Que significa la etapa**, independiente de
    #: como la llame la empresa: sin esto, "¿cuantos ganamos?" habria que
    #: contestarlo comparando nombres escritos a mano.
    kind: Mapped[str] = mapped_column(String(8), nullable=False, server_default="open")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class CrmCompany(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "crm_companies"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    #: Sin exigirlo: a un prospecto se le sigue la pista antes de tener su RUT,
    #: y pedirlo obligaria a inventarlo para poder anotarlo.
    rut: Mapped[str | None] = mapped_column(String(20))
    industry: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(240))
    #: El puente hacia `contracts`. Nulo mientras es prospecto.
    client_tenant_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="prospect")
    owner_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    notes: Mapped[str | None] = mapped_column(Text)


class CrmContact(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "crm_contacts"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    crm_company_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    email: Mapped[str | None] = mapped_column(String(240))
    phone: Mapped[str | None] = mapped_column(String(40))
    role_title: Mapped[str | None] = mapped_column(String(120))
    #: A quien se le escribe por defecto. **Uno solo por empresa**, y lo impide
    #: un indice unico parcial: dos principales no es un dato, es la ausencia
    #: de una decision.
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class CrmDeal(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "crm_deals"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    crm_company_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_companies.id", ondelete="CASCADE"), nullable=False
    )
    crm_contact_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_contacts.id", ondelete="SET NULL")
    )
    stage_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_stages.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    #: `Numeric` y no `float`: el dinero con coma flotante acumula centavos
    #: fantasma, y un pipeline que no cuadra con la propuesta firmada no sirve.
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="CLP")
    owner_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    expected_close_date: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Obligatorio al perder. La razon de tener un pipeline es aprender por que
    #: se pierde, y un perdido sin motivo no ensena nada.
    lost_reason: Mapped[str | None] = mapped_column(Text)
    #: El contrato en que termino, cuando se gano y el cliente entro (#82).
    contract_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id")
    )


class CrmActivity(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Una llamada, un correo, una reunion o una nota.

    **Cuelga de exactamente uno** de los tres padres, y lo exige un CHECK en la
    base. Se usan tres claves foraneas y no el par `(entity_type, entity_id)` de
    `entity_documents`: los padres posibles son tres y conocidos, asi que se
    gana integridad referencial de verdad. Con el par polimorfico, borrar una
    empresa deja actividades apuntando al vacio y nada lo impide.
    """

    __tablename__ = "crm_activities"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    author_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    crm_company_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_companies.id", ondelete="CASCADE")
    )
    crm_contact_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_contacts.id", ondelete="CASCADE")
    )
    crm_deal_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_deals.id", ondelete="CASCADE")
    )
