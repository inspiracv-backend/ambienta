"""La cartera de un Gestor (#59, RF-65)."""
from datetime import date

from pydantic import BaseModel


class ClienteDeLaCartera(BaseModel):
    """Una empresa que este gestor administra, vigente o no."""

    tenant_id: str
    legal_name: str
    contract_id: str
    contract_number: str
    contract_status: str
    start_date: date | None
    end_date: date | None
    #: Si hoy se puede mandar `X-Cliente-Id` con este identificador.
    #:
    #: **Va explicito y la lista no se filtra**: un cliente cuyo contrato vencio
    #: tiene que verse, con su motivo. Desaparecer de la cartera se leeria como
    #: que se perdio al cliente, que es otra cosa.
    puede_actuar: bool
