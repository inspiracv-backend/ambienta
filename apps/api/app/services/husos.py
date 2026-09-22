"""En que dia del calendario vive cada empresa.

## Por que esto es un modulo y no una linea

Porque el mismo error ya aparecio dos veces en un dia, y las dos con la misma
forma: **una fecha de calendario comparada contra el reloj del servidor**.

1. El cron de avisos buscaba los vencimientos en una banda de horas alrededor de
   un instante. Un plazo vence a las 23:59 y el cron corre a las 07:00: no se
   avisaba nunca.
2. `contracts.end_date` se comparaba con `date.today()`. La base corre en UTC y
   el host en hora de Chile, asi que a partir de las 20:00 **los dos estan en
   dias distintos** — y un contrato vencido ayer seguia habilitando acceso
   durante esas cuatro horas.

Los dos son el mismo malentendido: `date.today()` no es "hoy", es "hoy donde
esta corriendo este proceso". Para una empresa chilena, un plazo peruano o un
contrato mexicano, eso puede ser otro dia.

`countries.default_timezone` tiene **cinco husos distintos**, asi que esto no es
una constante disfrazada.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.organization import Country, Tenant

#: Huso al que se cae si la empresa no tiene pais con huso declarado.
#:
#: Chile porque es el mercado del producto, pero **no da igual**: es el huso el
#: que decide en que dia cae una fecha de fin de dia, y con el equivocado el
#: sistema se adelanta o se atrasa un dia.
HUSO_POR_DEFECTO = "America/Santiago"


def huso_de(db: Session, tenant_id: UUID) -> str:
    """El huso horario de la empresa, via el pais al que pertenece."""
    nombre = db.scalar(
        select(Country.default_timezone)
        .join(Tenant, Tenant.country_id == Country.id)
        .where(Tenant.id == tenant_id)
    )
    return nombre or HUSO_POR_DEFECTO


def hoy_de(db: Session, tenant_id: UUID, ahora: datetime | None = None) -> date:
    """Que dia es **para esta empresa**.

    Es lo que hay que usar para decidir si una fecha de calendario ya paso:
    vencimientos, fechas de contrato, plazos. Nunca `date.today()`, que responde
    por el proceso y no por la empresa.
    """
    ahora = ahora or datetime.now(timezone.utc)
    return ahora.astimezone(ZoneInfo(huso_de(db, tenant_id))).date()
