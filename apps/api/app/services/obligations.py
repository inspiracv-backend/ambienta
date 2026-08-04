"""Lógica de negocio para obligaciones y vencimientos."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from ..models.obligations import Obligation, Task
from ..models.notifications import Notification


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
    obl = db.get(Obligation, obligation_id)
    if not obl:
        raise ValueError("Obligation not found")

    obl.status = "fulfilled"
    if receipt:
        obl.external_receipt = receipt
    db.flush()
    db.refresh(obl)
    return obl


def create_deadline_notifications(
    db: Session, tenant_id: UUID, days_before: list[int] | None = None
) -> list[Notification]:
    if days_before is None:
        days_before = [30, 15, 7, 1]

    now = datetime.now(timezone.utc)
    created: list[Notification] = []

    for days in days_before:
        target_date = now + timedelta(days=days)
        window_start = target_date - timedelta(hours=12)
        window_end = target_date + timedelta(hours=12)

        obligations = db.scalars(
            select(Obligation).where(
                and_(
                    Obligation.tenant_id == tenant_id,
                    Obligation.status.in_(["open", "draft"]),
                    Obligation.due_at >= window_start,
                    Obligation.due_at <= window_end,
                    Obligation.deleted_at.is_(None),
                )
            )
        ).all()

        for obl in obligations:
            if not obl.owner_user_id:
                continue

            notif = Notification(
                tenant_id=tenant_id,
                recipient_user_id=obl.owner_user_id,
                channel="in_app",
                subject=f"Vencimiento en {days} días: {obl.title}",
                body=f"La obligación '{obl.title}' (código {obl.code}) vence el {obl.due_at.strftime('%d/%m/%Y') if obl.due_at else 'N/A'}.",
                status="queued",
                context={"obligation_id": str(obl.id), "days_before": days},
            )
            db.add(notif)
            created.append(notif)

    db.flush()
    return created
