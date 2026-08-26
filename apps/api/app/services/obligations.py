"""Lógica de negocio para obligaciones y vencimientos."""
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models.notifications import Notification
from ..models.obligations import DeclarationTemplate, Obligation
from ..models.catalog import RetcSystem
from .declaracion import urgencia


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


def _plantilla_de(db: Session, obl: Obligation) -> DeclarationTemplate | None:
    """La plantilla Excel vigente del sistema ante el que declara esta obligacion.

    Devuelve `None` sin ruido en tres casos legitimos: la obligacion no declara
    sistema, el sistema no tiene plantilla cargada, o la que hay no esta
    vigente. **Hoy los tres son el caso normal**: `declaration_templates` tiene
    cero filas — el repositorio de plantillas (#116) es contenido oficial que
    todavia no se cargo, no codigo que falte.

    La vigencia se filtra por fecha y no solo por `active`: una plantilla
    marcada activa cuyo `valid_to` ya paso corresponde a una estructura que el
    portal dejo de aceptar, y adjuntarla haria que la empresa preparara su
    declaracion en un formato que le van a rechazar.
    """
    if obl.retc_system_id is None:
        return None

    hoy = date.today()
    return db.scalar(
        select(DeclarationTemplate)
        .join(RetcSystem, RetcSystem.code == DeclarationTemplate.system_code)
        .where(
            RetcSystem.id == obl.retc_system_id,
            DeclarationTemplate.active.is_(True),
            DeclarationTemplate.deleted_at.is_(None),
            or_(DeclarationTemplate.valid_from.is_(None), DeclarationTemplate.valid_from <= hoy),
            or_(DeclarationTemplate.valid_to.is_(None), DeclarationTemplate.valid_to >= hoy),
        )
        .order_by(DeclarationTemplate.valid_from.desc().nulls_last())
    )


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

            # La plantilla del sistema ante el que se declara (#117). Va en el
            # contexto y **no pegada en el cuerpo**: quien envie el correo
            # necesita el id para adjuntar el archivo, no su nombre en una
            # frase. Si la obligacion no declara sistema, o ese sistema no
            # tiene plantilla vigente, el aviso sale igual — un recordatorio
            # sin adjunto sigue sirviendo; uno que no se envia, no.
            plantilla = _plantilla_de(db, obl)

            contexto = {
                "obligation_id": str(obl.id),
                "days_before": days,
                "urgencia": urgencia(obl, now).nivel,
            }
            if plantilla is not None:
                contexto["template_id"] = str(plantilla.id)
                contexto["template_name"] = plantilla.name
                contexto["template_version"] = plantilla.version

            notif = Notification(
                tenant_id=tenant_id,
                recipient_user_id=obl.owner_user_id,
                channel="in_app",
                subject=f"Vencimiento en {days} días: {obl.title}",
                body=f"La obligación '{obl.title}' (código {obl.code}) vence el {obl.due_at.strftime('%d/%m/%Y') if obl.due_at else 'N/A'}.",
                status="queued",
                context=contexto,
            )
            db.add(notif)
            created.append(notif)

    db.flush()
    return created
