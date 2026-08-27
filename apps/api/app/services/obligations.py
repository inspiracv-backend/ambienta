"""Lógica de negocio para obligaciones y vencimientos."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from ..models.notifications import Notification
from ..models.obligations import Obligation


def get_upcoming_obligations(
    db: Session, tenant_id: UUID, days_ahead: int = 30
) -> list[Obligation]:
    cutoff = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    stmt = (
        select(Obligation)
        .where(
            and_(
                Obligation.tenant_id == tenant_id,
                Obligation.status.in_(["open", "draft"]),
                Obligation.due_at <= cutoff,
                Obligation.due_at > datetime.now(timezone.utc),
                Obligation.deleted_at.is_(None),
            )
        )
        .order_by(Obligation.due_at)
    )
    return list(db.scalars(stmt).all())


def get_overdue_obligations(db: Session, tenant_id: UUID) -> list[Obligation]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(Obligation)
        .where(
            and_(
                Obligation.tenant_id == tenant_id,
                Obligation.status.in_(["open", "draft"]),
                Obligation.due_at < now,
                Obligation.deleted_at.is_(None),
            )
        )
        .order_by(Obligation.due_at)
    )
    return list(db.scalars(stmt).all())


def submit_obligation(
    db: Session, obligation_id: UUID, user_id: UUID
) -> Obligation:
    obl = db.get(Obligation, obligation_id)
    if not obl:
        raise ValueError("Obligation not found")
    if obl.status not in ("open", "draft"):
        raise ValueError(f"Cannot submit obligation in status '{obl.status}'")

    obl.status = "submitted"
    obl.submitted_at = datetime.now(timezone.utc)
    db.flush()
    db.refresh(obl)
    return obl


def fulfill_obligation(
    db: Session, obligation_id: UUID, receipt: str | None = None
) -> Obligation:
    """Registra el folio. **Ya no inventa un estado que la base rechaza.**

    Escribia `status = "fulfilled"`, que no esta en el CHECK de `obligations`:
    el endpoint respondia 422 en el 100 % de los casos. Ahora delega en
    `services/declaracion.py`, que es donde vive el flujo entero.

    Se conserva la funcion porque tenia llamadores; lo que no se conserva es la
    segunda definicion del flujo.
    """
    from .declaracion import registrar_folio

    obl = db.get(Obligation, obligation_id)
    if not obl:
        raise ValueError("Obligation not found")
    if not receipt:
        raise ValueError("Hace falta el folio que devolvio el sistema oficial.")
    return registrar_folio(db, obligacion=obl, folio=receipt)


def create_deadline_notifications(
    db: Session, tenant_id: UUID, days_before: list[int] | None = None
) -> list[Notification]:
    """**Obsoleta. Usa `services/avisos_de_vencimiento.generar()`.**

    Se conserva porque tenia llamadores, pero delega: mantener dos generadores
    de avisos es garantizar que uno de los dos duplique, escale mal, o ignore
    las reglas de la empresa — que es exactamente lo que hacia este.

    Los tres defectos que tenia, medidos con sondas:

    1. **Duplicaba.** Tres corridas seguidas dejaban tres avisos identicos.
    2. **`if not obl.owner_user_id: continue`** — las obligaciones sin
       responsable no avisaban a nadie, en silencio. En el seed son 3 de 8.
    3. Las ventanas escritas a mano (`[30, 15, 7, 1]`) mientras
       `notification_rules` existia vacia y nadie la leia.

    Devuelve una lista para no romper a quien esperaba `len(...)`, pero el
    resultado util —cuantos se omitieron por repetidos, cuantos escalaron, y
    **cuales no avisaron a nadie**— solo lo da el servicio nuevo.
    """
    from .avisos_de_vencimiento import generar

    ventanas = tuple(days_before) if days_before else None
    r = generar(db, tenant_id, ventanas=ventanas)
    # Se devuelven los avisos de esta corrida, que es lo que la firma promete.
    return list(db.new)[: r.creados] if r.creados else []
