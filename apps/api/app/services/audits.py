"""Lógica de negocio para auditorías y no conformidades."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from ..models.audit import ActionPlan, Audit, AuditItem, Nonconformity
from ..models.compliance import ArticleCompliance


#: El ciclo de vida de una auditoria, con **el vocabulario de la base**.
#:
#: Hasta el 4-sep esta tabla decia `in_progress`, `fieldwork` y `review`, tres
#: estados que el CHECK de `audits.status` no admite: son
#: `planned|active|reporting|closed|cancelled`. La consecuencia era que
#: `POST /audits/{id}/advance` **fallaba en todos los avances**:
#:
#: | intento | resultado |
#: |---|---|
#: | planned -> in_progress | 422, `audits_status_check` |
#: | planned -> active | 400, "no permitida" |
#: | planned -> cancelled | 200 |
#:
#: O sea que lo unico que se podia hacer con una auditoria era cancelarla, y
#: los dos errores se leen distinto —uno como dato invalido, otro como una
#: transicion prohibida— asi que ninguno apunta a la causa. Misma familia que
#: `fulfill` escribiendo un estado fuera del CHECK.
#:
#: La base manda: es lo que dicen `db/01_schema.sql`, el dump y el mapa
#: `ESTADO_POR_STATUS` del frontend. Cambiar el CHECK en vez de esto habria
#: dejado a la pantalla traduciendo estados que ya no existen.
AUDIT_STATUS_TRANSITIONS = {
    "planned": ["active", "cancelled"],
    "active": ["reporting", "cancelled"],
    "reporting": ["closed", "cancelled"],
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

    if new_status == "active" and not audit.actual_start:
        audit.actual_start = datetime.now(timezone.utc)
    if new_status == "closed":
        audit.actual_end = datetime.now(timezone.utc)

    audit.status = new_status
    db.flush()
    db.refresh(audit)
    return audit


#: El estado que significa "alguien verifico que la accion funciono".
#:
#: Es el unico que habilita el cierre, y por eso vive en una constante: la
#: condicion de §10.2.1 d) no puede quedar como una cadena suelta dentro de un
#: filtro.
ESTADO_VERIFICADO = "verified"

#: Estados que **no** cuentan como trabajo pendiente al cerrar.
#:
#: `cancelled` esta aca porque cancelar es decidir que ese trabajo no se hace, y
#: eso no es algo que quede por hacer. Antes bloqueaba el cierre para siempre, y
#: sin salida: el unico estado que dejaba pasar era `verified`, y un plan
#: cancelado no se puede verificar.
#:
#: **Todos tienen que existir en el CHECK de `action_plans.status`.** La version
#: anterior nombraba `closed`, que la base no admite — un filtro sobre un valor
#: imposible no falla, simplemente no coincide nunca. Hay una prueba que lo
#: contrasta contra la restriccion real.
ESTADOS_QUE_NO_BLOQUEAN = (ESTADO_VERIFICADO, "cancelled")


class SinVerificarLaEficacia(ValueError):
    """Cerrar exige una verificacion de eficacia afirmativa (§10.2.1 d)."""


def close_nonconformity(
    db: Session,
    nc_id: UUID,
    closure_notes: str,
    user_id: UUID | None = None,
) -> Nonconformity:
    """Cierra un registro de mejora, **si se verifico que la accion funciono**.

    ## Por que no basta con que no queden planes pendientes

    Es lo que hacia antes, y dejaba pasar el caso peor: un registro **sin un
    solo plan de accion** cerraba sin que nadie hubiera verificado nada. Para el
    sistema quedaba idéntico a uno tratado y verificado, y esa es justamente la
    diferencia que un auditor viene a revisar.

    El spec lo pide sin ambiguedad —"una verificacion de eficacia **afirmativa**
    antes de permitir el cierre"— y agrega la distincion que importa: *sin
    responder no es lo mismo que responder que no*. Cero verificaciones no es una
    verificacion negativa; es que nadie miro.

    ## Las dos condiciones

    1. **Nada pendiente.** Ningun plan en un estado que signifique trabajo por
       hacer. Cancelado no cuenta: ver `ESTADOS_QUE_NO_BLOQUEAN`.
    2. **Al menos una verificacion afirmativa.** Un plan `verified`.

    Completar la accion y verificar que sirvio son cosas distintas, y §10.2.1
    pide las dos. Un plan `completed` cumple la primera y no la segunda.
    """
    nc = db.get(Nonconformity, nc_id)
    if not nc:
        raise ValueError("Nonconformity not found")
    if nc.status == "closed":
        raise ValueError("Nonconformity already closed")

    planes = db.scalars(
        select(ActionPlan).where(
            and_(
                ActionPlan.nonconformity_id == nc_id,
                ActionPlan.deleted_at.is_(None),
            )
        )
    ).all()

    pendientes = [p for p in planes if p.status not in ESTADOS_QUE_NO_BLOQUEAN]
    if pendientes:
        raise SinVerificarLaEficacia(
            f"No se puede cerrar: {len(pendientes)} plan(es) de accion siguen "
            "abiertos. Hay que terminarlos y verificar que la accion funciono."
        )

    if not any(p.status == ESTADO_VERIFICADO for p in planes):
        raise SinVerificarLaEficacia(
            "No se puede cerrar: nadie verifico que la accion funciono. "
            "Cerrar exige una verificacion de eficacia afirmativa (ISO 14001 "
            "10.2.1 d). Sin planes verificados no hay nada que respalde el "
            "cierre ante una auditoria."
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
        plan.status = ESTADO_VERIFICADO
        plan.verified_at = datetime.now(timezone.utc)
        plan.verified_by = verified_by
    else:
        # **Se limpia la firma anterior.** Un plan que ya se habia verificado y
        # cuya verificacion posterior concluye que no funciono volveria a
        # `in_progress` **conservando `verified_at` y `verified_by`**: una firma
        # que dice que alguien verifico que esto sirve, sobre un trabajo que se
        # reabrio justamente porque no sirvio.
        #
        # No lo aprovecha el cierre —mira `status`, no la fecha— pero es lo que
        # se muestra en la ficha y lo que se exporta a un auditor.
        plan.status = "in_progress"
        plan.verified_at = None
        plan.verified_by = None

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
