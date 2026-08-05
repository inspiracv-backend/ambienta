"""Metricas agregadas del Dashboard (S-06 y S-07, RF-47 a RF-49).

Todo se resuelve con COUNT y GROUP BY en la base. Los servicios de
`obligations.py` y `compliance.py` devuelven entidades completas, que sirven
para listar pero no para contar: traer 500 obligaciones al proceso de Python
para hacer `len()` es trabajo que Postgres ya sabe hacer solo.

El aislamiento por tenant lo da RLS (`get_tenant_db` abre la transaccion con
`SET LOCAL ROLE ambienta_app`). Igual se filtra por `tenant_id` de forma
explicita, como exige CLAUDE.md §4: RLS es la segunda barrera, no la unica.

Spec: openspec/changes/dashboard-metricas-api/design.md
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ..models.audit import Nonconformity
from ..models.compliance import ArticleCompliance, MatrixNorm, TenantLegalMatrix
from ..models.obligations import Obligation
from ..models.organization import Facility

# Una obligacion deja de pesar cuando se acepta o se cierra. El resto de los
# estados —draft, open, in_progress, submitted, rejected, overdue— siguen
# siendo trabajo pendiente para alguien.
#
# `obligations.py` cuenta solo ('open','draft'), lo que deja fuera a
# `in_progress` y `submitted`: una obligacion en la que alguien ya empezo a
# trabajar desaparecia del tablero. Aca se cuenta por exclusion para que
# agregar un estado nuevo al CHECK no vuelva a abrir ese hueco en silencio.
OBLIGACION_RESUELTA = ("accepted", "closed")

# Una NC se apaga al cerrarse o al rechazarse (no procedia).
NC_RESUELTA = ("closed", "rejected")


def _condiciones_pendientes(
    tenant_id: UUID, facility_id: UUID | None = None
) -> list[ColumnElement[bool]]:
    """Las condiciones, no la consulta.

    Devolver condiciones y no un `select()` ya armado permite reusarlas tanto
    para traer entidades como para agregar con COUNT. Envolver el select de
    entidades en una subconsulta no sirve: dentro de `select_from(subq)` las
    columnas de `Obligation` quedan fuera de alcance y los `.filter()` de los
    agregados no correlacionan.
    """
    condiciones: list[ColumnElement[bool]] = [
        Obligation.tenant_id == tenant_id,
        Obligation.status.notin_(OBLIGACION_RESUELTA),
        Obligation.deleted_at.is_(None),
    ]
    if facility_id is not None:
        condiciones.append(Obligation.facility_id == facility_id)
    return condiciones


def _cumplimiento_global(db: Session, tenant_id: UUID) -> dict:
    """% de cumplimiento sobre los articulos evaluados del tenant.

    `article_compliance.compliance_status` admite cinco valores:
    compliant, non_compliant, partial, not_applicable y pending.

    Los `not_applicable` salen del denominador: un requisito que no aplica no
    puede cumplirse ni incumplirse, y dejarlo dentro hunde el indicador de
    cualquier empresa a la que le apliquen pocos articulos de una norma
    grande.

    Los `pending` SI cuentan en el denominador. Es deliberado: si no, una
    matriz con un solo articulo evaluado y cumplido mostraria 100%, que es
    exactamente la lectura que un auditor no deberia poder sacar del tablero.

    Los `partial` cuentan en el denominador pero no en el numerador. Dos
    cumplimientos parciales no equivalen a uno completo, y sumarlos como medio
    punto cada uno inventaria una precision que la evaluacion no tiene.
    """
    total, cumplen, incumplen = db.execute(
        select(
            func.count(ArticleCompliance.id).filter(
                ArticleCompliance.compliance_status != "not_applicable"
            ),
            func.count(ArticleCompliance.id).filter(
                ArticleCompliance.compliance_status == "compliant"
            ),
            func.count(ArticleCompliance.id).filter(
                ArticleCompliance.compliance_status == "non_compliant"
            ),
        )
        .select_from(ArticleCompliance)
        .join(MatrixNorm, MatrixNorm.id == ArticleCompliance.matrix_norm_id)
        .join(TenantLegalMatrix, TenantLegalMatrix.id == MatrixNorm.matrix_id)
        .where(
            and_(
                TenantLegalMatrix.tenant_id == tenant_id,
                ArticleCompliance.deleted_at.is_(None),
                MatrixNorm.deleted_at.is_(None),
                TenantLegalMatrix.deleted_at.is_(None),
            )
        )
    ).one()

    pct = round(cumplen / total * 100, 1) if total else 0.0
    return {
        "compliance_percentage": pct,
        "articles_evaluated": total,
        "articles_non_compliant": incumplen,
    }


def _cumplimiento_por_facility(db: Session, tenant_id: UUID) -> dict[UUID, dict]:
    """Lo mismo que arriba pero agrupado, en una sola consulta.

    `ArticleCompliance.facility_id` es nullable: un articulo evaluado a nivel
    de empresa no cuelga de ninguna planta. Esos quedan fuera del desglose por
    planta a proposito — repartirlos entre todas seria inventar un dato.
    """
    filas = db.execute(
        select(
            ArticleCompliance.facility_id,
            func.count(ArticleCompliance.id).filter(
                ArticleCompliance.compliance_status != "not_applicable"
            ),
            func.count(ArticleCompliance.id).filter(
                ArticleCompliance.compliance_status == "compliant"
            ),
            func.count(ArticleCompliance.id).filter(
                ArticleCompliance.compliance_status == "non_compliant"
            ),
        )
        .select_from(ArticleCompliance)
        .join(MatrixNorm, MatrixNorm.id == ArticleCompliance.matrix_norm_id)
        .join(TenantLegalMatrix, TenantLegalMatrix.id == MatrixNorm.matrix_id)
        .where(
            and_(
                TenantLegalMatrix.tenant_id == tenant_id,
                ArticleCompliance.facility_id.is_not(None),
                ArticleCompliance.deleted_at.is_(None),
                MatrixNorm.deleted_at.is_(None),
                TenantLegalMatrix.deleted_at.is_(None),
            )
        )
        .group_by(ArticleCompliance.facility_id)
    ).all()

    return {
        fid: {
            "compliance_percentage": round(ok / total * 100, 1) if total else 0.0,
            "articles_non_compliant": malos,
        }
        for fid, total, ok, malos in filas
    }


def _nc_abiertas_por_facility(db: Session, tenant_id: UUID) -> dict[UUID | None, int]:
    filas = db.execute(
        select(Nonconformity.facility_id, func.count(Nonconformity.id))
        .where(
            and_(
                Nonconformity.tenant_id == tenant_id,
                Nonconformity.status.notin_(NC_RESUELTA),
                Nonconformity.deleted_at.is_(None),
            )
        )
        .group_by(Nonconformity.facility_id)
    ).all()
    return {fid: n for fid, n in filas}


def _dias_restantes(due_at: datetime, ahora: datetime) -> int:
    """Dias que faltan, redondeando hacia arriba.

    Se redondea hacia arriba y no con `timedelta.days` (que trunca) para que
    coincida con el `Math.ceil` que el frontend ya usaba en la tarjeta hero.
    Con truncamiento, algo que vence en 20 horas se leeria "0 dias restantes"
    en la API y "1 dia" en pantalla: dos numeros distintos para el mismo dato.

    Negativo si ya vencio.
    """
    return math.ceil((due_at - ahora).total_seconds() / 86400)


def _proximas_por_facility(
    db: Session, tenant_id: UUID, ahora: datetime
) -> dict[UUID | None, dict]:
    """La obligacion pendiente mas proxima a vencer, por planta.

    Se ordena por `due_at` ascendente y se toma la primera de cada grupo con
    DISTINCT ON, que en Postgres resuelve el "top 1 por grupo" sin subconsulta
    ni window function.
    """
    filas = (
        db.execute(
            select(Obligation)
            .where(
                and_(
                    *_condiciones_pendientes(tenant_id),
                    Obligation.due_at.is_not(None),
                )
            )
            .order_by(Obligation.facility_id, Obligation.due_at)
            .distinct(Obligation.facility_id)
        )
        .scalars()
        .all()
    )

    return {
        o.facility_id: {
            "obligation_id": str(o.id),
            "code": o.code,
            "title": o.title,
            "due_at": o.due_at.isoformat() if o.due_at else None,
            "days_remaining": _dias_restantes(o.due_at, ahora) if o.due_at else None,
            "status": o.status,
        }
        for o in filas
    }


def get_dashboard_metrics(
    db: Session,
    tenant_id: UUID,
    facility_id: UUID | None = None,
    days_ahead: int = 30,
) -> dict:
    """Todo lo que S-06 y S-07 necesitan, en una sola llamada."""
    ahora = datetime.now(timezone.utc)
    corte = ahora + timedelta(days=days_ahead)

    # Un solo viaje a la base para los tres contadores de obligaciones.
    total_pendientes, por_vencer, vencidas = db.execute(
        select(
            func.count(Obligation.id),
            func.count(Obligation.id).filter(
                and_(Obligation.due_at > ahora, Obligation.due_at <= corte)
            ),
            func.count(Obligation.id).filter(Obligation.due_at < ahora),
        ).where(and_(*_condiciones_pendientes(tenant_id, facility_id)))
    ).one()

    nc_por_planta = _nc_abiertas_por_facility(db, tenant_id)
    nc_abiertas = (
        nc_por_planta.get(facility_id, 0)
        if facility_id is not None
        else sum(nc_por_planta.values())
    )

    global_ = _cumplimiento_global(db, tenant_id)
    proximas = _proximas_por_facility(db, tenant_id, ahora)

    if facility_id is not None:
        critica = proximas.get(facility_id)
    else:
        # La mas proxima de todas las plantas, incluida la que no tiene planta.
        candidatas = [p for p in proximas.values() if p["due_at"]]
        critica = min(candidatas, key=lambda p: p["due_at"]) if candidatas else None

    # La lista de "proximos vencimientos" de S-06 sale de las mismas filas que
    # ya se trajeron para el critico: son la obligacion mas urgente de cada
    # planta, que es exactamente lo que corresponde mostrar. Ordenarlas aca no
    # cuesta una consulta mas.
    proximos = sorted(
        (p for p in proximas.values() if p["due_at"]),
        key=lambda p: p["due_at"],
    )[:5]

    return {
        "tenant_id": str(tenant_id),
        "generated_at": ahora.isoformat(),
        "upcoming_deadlines": proximos,
        "global": {
            **global_,
            "total_obligations": total_pendientes,
            "nc_open": nc_abiertas,
            "obligations_upcoming": por_vencer,
            "obligations_overdue": vencidas,
        },
        "critical_deadline": critica,
        "facilities": _metricas_por_facility(
            db, tenant_id, facility_id, nc_por_planta, proximas
        ),
    }


def _metricas_por_facility(
    db: Session,
    tenant_id: UUID,
    facility_id: UUID | None,
    nc_por_planta: dict,
    proximas: dict,
) -> list[dict]:
    """Una fila por planta para la tabla S-07.

    Se parte de las plantas y no de las obligaciones: una planta sin nada
    cargado tiene que aparecer igual, en 0. Si se partiera de las obligaciones,
    las plantas vacias desaparecerian del tablero, que es justo donde conviene
    que se vean.
    """
    stmt = select(Facility).where(
        and_(
            Facility.tenant_id == tenant_id,
            Facility.active.is_(True),
            Facility.deleted_at.is_(None),
        )
    )
    if facility_id is not None:
        stmt = stmt.where(Facility.id == facility_id)

    cumplimiento = _cumplimiento_por_facility(db, tenant_id)

    return [
        {
            "facility_id": str(f.id),
            "name": f.name,
            "commune_code": f.commune_code,
            "region_code": f.region_code,
            "compliance_percentage": cumplimiento.get(f.id, {}).get(
                "compliance_percentage", 0.0
            ),
            "non_compliant_count": cumplimiento.get(f.id, {}).get(
                "articles_non_compliant", 0
            ),
            "nc_open_count": nc_por_planta.get(f.id, 0),
            "critical_deadline": proximas.get(f.id),
        }
        for f in db.scalars(stmt.order_by(Facility.name)).all()
    ]
