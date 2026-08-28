"""Esquemas del CRM (epica #32).

Los valores de los enumerados son **los de la base**, no traducciones: los
CHECK de `db/22_crm.sql` mandan. Traducirlos aca crearia un tercer vocabulario
—despues del de la base y el de `packages/shared`— y este repositorio ya tiene
la leccion aprendida de que dos se desincronizan solos.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from .base import OrmBase

# ── Etapas del pipeline ───────────────────────────────────────────────────


class CrmStageCreate(BaseModel):
    code: str
    name: str
    position: int = 0
    #: `open` | `won` | `lost`. Que significa la etapa para el sistema,
    #: independiente de como la llame la empresa.
    kind: str = "open"
    active: bool = True


class CrmStageUpdate(BaseModel):
    name: str | None = None
    position: int | None = None
    kind: str | None = None
    active: bool | None = None


class CrmStageRead(OrmBase):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    position: int
    kind: str
    active: bool


# ── Empresas ──────────────────────────────────────────────────────────────


class CrmCompanyCreate(BaseModel):
    name: str
    rut: str | None = None
    industry: str | None = None
    website: str | None = None
    status: str = "prospect"
    owner_user_id: UUID | None = None
    notes: str | None = None
    #: **No se acepta del cuerpo.** Ver `CrmCompanyUpdate`.


class CrmCompanyUpdate(BaseModel):
    name: str | None = None
    rut: str | None = None
    industry: str | None = None
    website: str | None = None
    status: str | None = None
    owner_user_id: UUID | None = None
    notes: str | None = None
    #: `client_tenant_id` **no esta aca a proposito.** Es una clave foranea a
    #: `tenants`, y las claves foraneas no pasan por RLS: aceptarla del cuerpo
    #: dejaria a una empresa enlazar su ficha con el tenant de otra. Se fija en
    #: el endpoint de promocion (#82), que comprueba a que tenant corresponde.


class CrmCompanyRead(OrmBase):
    id: UUID
    tenant_id: UUID
    name: str
    rut: str | None
    industry: str | None
    website: str | None
    client_tenant_id: UUID | None
    status: str
    owner_user_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ── Contactos ─────────────────────────────────────────────────────────────


class CrmContactCreate(BaseModel):
    crm_company_id: UUID
    full_name: str
    email: str | None = None
    phone: str | None = None
    role_title: str | None = None
    is_primary: bool = False


class CrmContactUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    role_title: str | None = None
    is_primary: bool | None = None


class CrmContactRead(OrmBase):
    id: UUID
    tenant_id: UUID
    crm_company_id: UUID
    full_name: str
    email: str | None
    phone: str | None
    role_title: str | None
    is_primary: bool
    created_at: datetime


# ── Oportunidades ─────────────────────────────────────────────────────────


class CrmDealCreate(BaseModel):
    crm_company_id: UUID
    crm_contact_id: UUID | None = None
    #: Opcional: sin etapa, entra en la primera del pipeline de la empresa. Un
    #: trato que no se puede crear porque falta elegir columna es un trato que
    #: se anota en un papel.
    stage_id: UUID | None = None
    title: str
    amount: Decimal | None = None
    currency: str = "CLP"
    owner_user_id: UUID | None = None
    expected_close_date: date | None = None


class CrmDealUpdate(BaseModel):
    crm_contact_id: UUID | None = None
    title: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    owner_user_id: UUID | None = None
    expected_close_date: date | None = None
    #: `stage_id` **no esta aca**: mover de etapa tiene su propio endpoint
    #: porque no es editar un campo. Ganar cierra el trato, perder exige motivo,
    #: y las dos cosas se perderian en un `PATCH` generico.


class CrmDealRead(OrmBase):
    id: UUID
    tenant_id: UUID
    crm_company_id: UUID
    crm_contact_id: UUID | None
    stage_id: UUID
    title: str
    amount: Decimal | None
    currency: str
    owner_user_id: UUID | None
    expected_close_date: date | None
    closed_at: datetime | None
    lost_reason: str | None
    contract_id: UUID | None
    created_at: datetime
    updated_at: datetime


class MoverDeEtapa(BaseModel):
    """Arrastrar un trato a otra columna del kanban.

    `motivo` es **obligatorio si la etapa destino es de tipo `lost`**, y lo
    comprueba el servicio. Un trato perdido sin explicacion no ensena nada, y
    aprender por que se pierde es la razon de tener un pipeline.
    """

    stage_id: UUID
    motivo: str | None = None


class ResultadoMover(BaseModel):
    deal: CrmDealRead
    #: Que hizo el movimiento ademas de cambiar la columna: cerrar el trato,
    #: reabrirlo, anotar el motivo. Se devuelve para que la pantalla pueda
    #: decirlo en vez de que la persona lo descubra recargando.
    efectos: list[str] = Field(default_factory=list)


# ── Actividades ───────────────────────────────────────────────────────────


class CrmActivityCreate(BaseModel):
    """Una llamada, un correo, una reunion o una nota.

    **Exactamente uno** de los tres padres. Lo exige un CHECK en la base y lo
    comprueba el servicio antes, para responder un 422 legible en vez de un
    error de restriccion.
    """

    kind: str
    subject: str
    body: str | None = None
    occurred_at: datetime | None = None
    crm_company_id: UUID | None = None
    crm_contact_id: UUID | None = None
    crm_deal_id: UUID | None = None


class CrmActivityUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    occurred_at: datetime | None = None


class CrmActivityRead(OrmBase):
    id: UUID
    tenant_id: UUID
    kind: str
    subject: str
    body: str | None
    occurred_at: datetime
    author_user_id: UUID | None
    crm_company_id: UUID | None
    crm_contact_id: UUID | None
    crm_deal_id: UUID | None
    created_at: datetime


# ── Vista del pipeline ────────────────────────────────────────────────────


class ColumnaDelPipeline(BaseModel):
    """Una columna del kanban, con lo que hace falta para dibujarla."""

    stage: CrmStageRead
    deals: list[CrmDealRead]
    #: Cuantos y cuanto suman. Va calculado aca y no en el navegador porque la
    #: lista puede venir cortada por el tope, y sumar lo que se ve daria un
    #: total menor que el real **sin que nada lo diga**.
    total_deals: int
    monto_total: Decimal


class PipelineRead(BaseModel):
    columnas: list[ColumnaDelPipeline]
    #: `true` = alguna columna se corto en el tope. Se dice, en vez de truncar
    #: en silencio: una lista cortada sin avisar se lee como "esto es todo".
    truncado: bool
