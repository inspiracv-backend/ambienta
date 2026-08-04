"""Lógica de negocio para auditorías y no conformidades."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from ..models.audit import ActionPlan, Audit, AuditItem, Nonconformity


AUDIT_STATUS_TRANSITIONS = {
    "planned": ["in_progress", "cancelled"],
    "in_progress": ["fieldwork", "cancelled"],
    "fieldwork": ["review", "cancelled"],
    "review": ["closed"],
    "closed": [],
    "cancelled": [],
}


def advance_audit_status(
    db: Session, audit_id: UUID, new_status: str, user_id: UUID | None = None
) -> Audit:
    audit = db.get(Audit, audit_id)
    if not audit:
        raise ValueError("Audit not found")

    allowed = AUDIT_STATUS_TRANSITIONS.get(audit.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{audit.status}' to '{new_status}'. "
            f"Allowed: {allowed}"
        )

    if new_status == "in_progress" and not audit.actual_start:
        audit.actual_start = datetime.now(timezone.utc)
    if new_status == "closed":
        audit.actual_end = datetime.now(timezone.utc)

    audit.status = new_status
    db.flush()
    db.refresh(audit)
    return audit


def close_nonconformity(
    db: Session,
    nc_id: UUID,
    closure_notes: str,
    user_id: UUID | None = None,
) -> Nonconformity:
    nc = db.get(Nonconformity, nc_id)
    if not nc:
        raise ValueError("Nonconformity not found")
    if nc.status == "closed":
        raise ValueError("Nonconformity already closed")

    open_plans = db.scalars(
        select(ActionPlan).where(
            and_(
                ActionPlan.nonconformity_id == nc_id,
                ActionPlan.status.notin_(["closed", "verified"]),
                ActionPlan.deleted_at.is_(None),
            )
        )
    ).all()

    if open_plans:
        raise ValueError(
            f"Cannot close: {len(open_plans)} action plan(s) still open"
        )

    nc.status = "closed"
    nc.closed_at = datetime.now(timezone.utc)
    nc.closure_notes = closure_notes
    db.flush()
    db.refresh(nc)
    return nc


def get_audit_summary(db: Session, audit_id: UUID) -> dict:
    audit = db.get(Audit, audit_id)
    if not audit:
        raise ValueError("Audit not found")

    items = db.scalars(
        select(AuditItem).where(
            and_(
                AuditItem.audit_id == audit_id,
                AuditItem.deleted_at.is_(None),
            )
        )
    ).all()

    result_counts: dict[str, int] = {}
    for item in items:
        result_counts[item.result] = result_counts.get(item.result, 0) + 1

    nc_count = db.scalar(
        select(func.count())
        .select_from(Nonconformity)
        .where(
            and_(
                Nonconformity.audit_item_id.in_([i.id for i in items]),
                Nonconformity.deleted_at.is_(None),
            )
        )
    ) or 0

    return {
        "audit_id": str(audit.id),
        "code": audit.code,
        "title": audit.title,
        "status": audit.status,
        "total_items": len(items),
        "results": result_counts,
        "nonconformities_count": nc_count,
    }


def verify_action_plan(
    db: Session,
    plan_id: UUID,
    verified_by: UUID,
    success: bool,
) -> ActionPlan:
    plan = db.get(ActionPlan, plan_id)
    if not plan:
        raise ValueError("Action plan not found")

    if success:
        plan.status = "verified"
        plan.verified_at = datetime.now(timezone.utc)
        plan.verified_by = verified_by
    else:
        plan.status = "in_progress"

    db.flush()
    db.refresh(plan)
    return plan
