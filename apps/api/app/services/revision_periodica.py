"""Cuando toca volver a evaluar cada norma de la matriz (ISO 14001 §9.1.2).

## Lo que habia

`matrix_norms.review_frequency` se declara en las siete normas del seed
—anual, semestral, trimestral— y `next_review_date` esta **vacia en las
siete**. La frecuencia existia y **nadie calculaba la fecha**: el mismo patron
que `due_date` en el registro de mejora. Y sin fecha, el calendario no puede
avisar que una evaluacion periodica vencio, que es lo que §9.1.2 exige.

## La regla

1. **Si la empresa declaro la fecha, manda la declarada.** Puede tener motivos
   —una auditoria agendada, un cambio normativo— que el sistema no conoce.
2. Si no, **se calcula**: la ultima evaluacion registrada mas la frecuencia.
3. Si no se puede calcular, **se dice por que** y no se inventa una fecha:
   nunca se evaluo, se evaluo sin fecha registrada, o la frecuencia es "por
   evento" (no es periodica).

**Se deriva, no se guarda.** Guardarla seria la forma mas corta de que una
evaluacion nueva deje la fecha vieja escrita: el mismo criterio que los conteos
del informe de auditoria.

**La fecha es de calendario, en el huso de la empresa.** `assessed_at` es un
instante; "evaluada el 2 de septiembre" es un dia en Chile, no en UTC. Ver
`husos.py`.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..models.catalog import LegalNorm
from ..models.compliance import ArticleCompliance, MatrixNorm, TenantLegalMatrix
from .husos import hoy_de, huso_de

#: Meses entre evaluaciones. `event_based` no esta a proposito: no es periodica.
MESES_POR_FRECUENCIA: dict[str, int] = {"quarterly": 3, "semiannual": 6, "annual": 12}

#: Por que una norma no tiene proxima revision. Van en la respuesta: una fila
#: sin fecha y sin motivo se lee como "no hay nada que hacer".
NUNCA_EVALUADA = "nunca_evaluada"
EVALUADA_SIN_FECHA = "evaluada_sin_fecha"
POR_EVENTO = "por_evento"


def sumar_meses(dia: date, meses: int) -> date:
    """El mismo dia `meses` despues; si ese mes no lo tiene, el ultimo del mes.

    31 de agosto + 6 meses es el 28 (o 29) de febrero, no el 3 de marzo: una
    revision semestral no puede correrse de mes.
    """
    total = dia.month - 1 + meses
    anio, mes = dia.year + total // 12, total % 12 + 1
    return date(anio, mes, min(dia.day, calendar.monthrange(anio, mes)[1]))


@dataclass(frozen=True)
class Revision:
    matrix_norm_id: UUID
    norm_id: UUID
    titulo: str
    frecuencia: str
    ultima_evaluacion: date | None
    proxima_revision: date | None
    #: `declarada` | `calculada` | `None`.
    origen: str | None
    motivo_sin_fecha: str | None
    vencida: bool


def proxima(
    frecuencia: str,
    declarada: date | None,
    ultima: date | None,
    hay_evaluaciones: bool,
) -> tuple[date | None, str | None, str | None]:
    """`(fecha, origen, motivo_sin_fecha)`. Separado para probarlo sin base."""
    if declarada is not None:
        return declarada, "declarada", None
    meses = MESES_POR_FRECUENCIA.get(frecuencia)
    if meses is None:
        return None, None, POR_EVENTO
    if ultima is not None:
        return sumar_meses(ultima, meses), "calculada", None
    return None, None, EVALUADA_SIN_FECHA if hay_evaluaciones else NUNCA_EVALUADA


def revisiones(db: Session, tenant_id: UUID) -> list[Revision]:
    """Una fila por norma aplicable de la matriz, lo mas urgente primero.

    Las `not_applicable` no se revisan: la evaluacion periodica es de lo que
    rige. Las `pending_analysis` si, porque justamente falta revisarlas.
    """
    huso = ZoneInfo(huso_de(db, tenant_id))
    hoy = hoy_de(db, tenant_id)

    evaluada = and_(
        ArticleCompliance.matrix_norm_id == MatrixNorm.id,
        ArticleCompliance.deleted_at.is_(None),
        ArticleCompliance.compliance_status != "pending",
    )
    filas = db.execute(
        select(
            MatrixNorm.id,
            MatrixNorm.norm_id,
            LegalNorm.title,
            LegalNorm.norm_number,
            MatrixNorm.review_frequency,
            MatrixNorm.next_review_date,
            func.max(ArticleCompliance.assessed_at),
            func.count(ArticleCompliance.id),
        )
        .join(TenantLegalMatrix, TenantLegalMatrix.id == MatrixNorm.matrix_id)
        .join(LegalNorm, LegalNorm.id == MatrixNorm.norm_id)
        .outerjoin(ArticleCompliance, evaluada)
        .where(
            MatrixNorm.deleted_at.is_(None),
            TenantLegalMatrix.deleted_at.is_(None),
            MatrixNorm.applicability != "not_applicable",
        )
        .group_by(
            MatrixNorm.id,
            MatrixNorm.norm_id,
            LegalNorm.title,
            LegalNorm.norm_number,
            MatrixNorm.review_frequency,
            MatrixNorm.next_review_date,
        )
    ).all()

    fuera: list[Revision] = []
    for mn_id, norm_id, titulo, numero, frecuencia, declarada, ultima_ts, evaluaciones in filas:
        ultima = ultima_ts.astimezone(huso).date() if ultima_ts is not None else None
        fecha, origen, motivo = proxima(frecuencia, declarada, ultima, evaluaciones > 0)
        fuera.append(
            Revision(
                matrix_norm_id=mn_id,
                norm_id=norm_id,
                titulo=titulo or numero or "",
                frecuencia=frecuencia,
                ultima_evaluacion=ultima,
                proxima_revision=fecha,
                origen=origen,
                motivo_sin_fecha=motivo,
                vencida=fecha is not None and fecha < hoy,
            )
        )
    # Con fecha primero, la mas proxima arriba; las sin fecha al final, que no
    # es lo mismo que "sin urgencia" pero no se pueden ordenar por un dia.
    fuera.sort(key=lambda r: (r.proxima_revision is None, r.proxima_revision or date.max, r.titulo))
    return fuera
