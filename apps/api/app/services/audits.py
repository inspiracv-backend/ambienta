"""Lógica de negocio para auditorías y no conformidades."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from ..models.audit import ActionPlan, Audit, AuditItem, Nonconformity
from ..models.compliance import ArticleCompliance


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


# ── Checklist de la auditoria y su cobertura (#36, RF-92/RF-93) ───────────

#: Cuantos items del checklist se devuelven. Un checklist se recorre en orden y
#: se responde punto por punto; con mas de esto no es un checklist, es otra
#: cosa. **Lo que se corta se dice** (`truncado`): una lista cortada en silencio
#: se lee como "esto es todo lo que hay que revisar", que sobre una auditoria es
#: exactamente la lectura que no puede darse.
TOPE_DE_ITEMS = 500


class ErrorDeChecklist(Exception):
    """La operacion pedida sobre el checklist no corresponde."""


class SecuenciaRepetida(ErrorDeChecklist):
    """Ese numero de orden ya existe en la auditoria."""


def items_de(db: Session, audit_id: UUID) -> tuple[list, bool]:
    """El checklist en su orden, y si se corto.

    Se ordena por `sequence` y no por fecha de creacion: el orden del checklist
    es parte del checklist — quien audita lo recorre de arriba abajo, y una
    pregunta fuera de sitio se salta.
    """
    filas = list(
        db.scalars(
            select(AuditItem)
            .where(
                AuditItem.audit_id == audit_id,
                AuditItem.deleted_at.is_(None),
            )
            .order_by(AuditItem.sequence)
            .limit(TOPE_DE_ITEMS + 1)
        ).all()
    )
    return filas[:TOPE_DE_ITEMS], len(filas) > TOPE_DE_ITEMS


def siguiente_secuencia(db: Session, audit_id: UUID) -> int:
    """El numero que sigue, para no obligar a llevarlo a mano.

    `uq_audit_items_seq` lo exige unico por auditoria, asi que dejarlo en manos
    de quien llama convierte un olvido en un error de restriccion.
    """
    ultimo = db.scalar(
        select(func.max(AuditItem.sequence)).where(AuditItem.audit_id == audit_id)
    )
    return (ultimo or 0) + 1


def cobertura(db: Session, audit: Audit) -> dict:
    """**Cuanto de lo aplicable miro esta auditoria de verdad.**

    Es el numero que falta para leer un resumen sin equivocarse. Sin el, una
    auditoria que reviso 3 de 50 requisitos y no encontro nada se lee
    **identica** a una que los reviso los 50 — las dos dicen "0 no conformes".

    El denominador son los articulos evaluados de la planta auditada; si la
    auditoria no declara planta, los de toda la empresa. El numerador son los
    **distintos** articulos que algun item del checklist referencia: dos
    preguntas sobre el mismo articulo no lo cubren dos veces.

    Los items **sin** articulo asociado no restan ni suman: son preguntas de
    proceso, legitimas, que no corresponden a un requisito legal concreto. Se
    informan aparte para que nadie las confunda con cobertura.
    """
    aplicables = select(func.count(func.distinct(ArticleCompliance.id))).where(
        ArticleCompliance.tenant_id == audit.tenant_id,
        ArticleCompliance.deleted_at.is_(None),
    )
    if audit.facility_id is not None:
        aplicables = aplicables.where(
            ArticleCompliance.facility_id == audit.facility_id
        )
    total = db.scalar(aplicables) or 0

    # **Sin `is_not(None)`, y no es un olvido.** `count(distinct x)` ya ignora
    # los nulos —medido: sobre `(1,1,null,null,2)` devuelve 2— asi que el
    # filtro no puede cambiar el resultado. Lo delato una mutacion que
    # sobrevivio: quitarlo no rompia ninguna prueba, porque no hacia nada.
    # Una condicion que no puede alterar la respuesta se lee como proteccion.
    cubiertos = db.scalar(
        select(func.count(func.distinct(AuditItem.article_compliance_id))).where(
            AuditItem.audit_id == audit.id,
            AuditItem.deleted_at.is_(None),
        )
    ) or 0

    sin_articulo = db.scalar(
        select(func.count(AuditItem.id)).where(
            AuditItem.audit_id == audit.id,
            AuditItem.deleted_at.is_(None),
            AuditItem.article_compliance_id.is_(None),
        )
    ) or 0

    return {
        "aplicables": total,
        "cubiertos": cubiertos,
        # **`None` y no cero cuando no hay nada aplicable.** Un 0 % ahi seria
        # una acusacion contra la empresa por algo que no existe: es el mismo
        # error del tablero con las plantas sin evaluar.
        "porcentaje": round(cubiertos * 100 / total, 1) if total else None,
        "items_sin_articulo": sin_articulo,
    }
