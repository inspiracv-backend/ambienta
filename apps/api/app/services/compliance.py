"""Lógica de negocio para la matriz de cumplimiento legal."""
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from ..models.compliance import ArticleCompliance, TenantLegalMatrix
from ..models.catalog import FacilityNormAssignment
from .resumen_cumplimiento import resumir


def get_compliance_stats(db: Session, matrix_id: UUID) -> dict:
    """Los totales de la matriz. **El calculo vive en `resumen_cumplimiento`.**

    Antes contaba aparte, y contaba mal en dos formas:

    - **Ignoraba `attributes.incluidoEnCalculo`** (RF-24), asi que excluir un
      articulo en la pantalla no movia el porcentaje. La funcionalidad existia y
      no hacia nada.
    - Metia `partial`, `not_applicable` y `pending` en la misma bolsa
      (`not_evaluated`), que son tres cosas distintas: cumplir a medias, no
      tener la obligacion, y no haber mirado todavia.

    Delega en `resumir()` en vez de arreglar la copia: dos calculos del mismo
    numero se desincronizan sin que nadie lo note, y quien mire el que este mal
    no tiene forma de saber cual era.

    `compliance_percentage` puede ser **`None`**: sin articulos que medir no es
    0 % —que significaria "no cumple nada"— sino que todavia no hay nada que
    medir.
    """
    matrix = db.get(TenantLegalMatrix, matrix_id)
    if not matrix:
        raise ValueError("Matrix not found")

    r = resumir(db, matrix_id)
    c = r.total

    return {
        "matrix_id": str(matrix_id),
        "period_year": matrix.period_year,
        "status": matrix.status,
        "total_norms": len(r.por_norma),
        "total_articles": c.evaluables + c.no_aplican + c.excluidos,
        "compliant": c.cumplen,
        "non_compliant": c.no_cumplen,
        "not_evaluated": c.sin_evaluar,
        "not_applicable": c.no_aplican,
        "excluded": c.excluidos,
        "evaluable_articles": c.evaluables,
        "evaluated_articles": c.evaluados,
        "compliance_percentage": c.porcentaje,
        # El que muestra la matriz en pantalla. Va acompanado de la cobertura:
        # solo, un 100 % sobre dos articulos evaluados de veinte engana.
        "compliance_percentage_of_evaluated": c.porcentaje_sobre_evaluados,
        "coverage_percentage": c.cobertura,
    }


def assign_norm_to_facility(
    db: Session,
    norm_id: UUID,
    facility_id: UUID,
    tenant_id: UUID,
    source: str = "manual",
) -> FacilityNormAssignment:
    existing = db.scalar(
        select(FacilityNormAssignment).where(
            and_(
                FacilityNormAssignment.norm_id == norm_id,
                FacilityNormAssignment.facility_id == facility_id,
                FacilityNormAssignment.deleted_at.is_(None),
            )
        )
    )
    if existing:
        raise ValueError("Norm already assigned to this facility")

    assignment = FacilityNormAssignment(
        norm_id=norm_id,
        facility_id=facility_id,
        tenant_id=tenant_id,
        source=source,
        assignment_status="active",
    )
    db.add(assignment)
    db.flush()
    db.refresh(assignment)
    return assignment


def evaluate_article(
    db: Session,
    article_compliance_id: UUID,
    answer: str,
    compliance_method: str | None = None,
    evidence_url: str | None = None,
    user_id: UUID | None = None,
) -> ArticleCompliance:
    art = db.get(ArticleCompliance, article_compliance_id)
    if not art:
        raise ValueError("Article compliance record not found")

    # Los cinco valores del CHECK de `article_compliance.compliance_status`
    # (db/01_schema.sql). Antes esta lista decia 'not_evaluated', que la base
    # rechaza, y omitia 'partial' y 'pending', que si acepta.
    valid_answers = [
        "compliant",
        "non_compliant",
        "partial",
        "not_applicable",
        "pending",
    ]
    if answer not in valid_answers:
        raise ValueError(f"Invalid answer. Must be one of: {valid_answers}")

    art.compliance_status = answer
    if compliance_method is not None:
        art.compliance_method = compliance_method
    if evidence_url is not None:
        art.evidence_url = evidence_url
    if user_id is not None:
        art.assessed_by = user_id
    art.assessed_at = func.now()

    db.flush()
    db.refresh(art)
    return art
