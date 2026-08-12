"""Lógica de negocio para la matriz de cumplimiento legal."""
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from ..models.compliance import ArticleCompliance, MatrixNorm, TenantLegalMatrix
from ..models.catalog import FacilityNormAssignment


def get_compliance_stats(db: Session, matrix_id: UUID) -> dict:
    matrix = db.get(TenantLegalMatrix, matrix_id)
    if not matrix:
        raise ValueError("Matrix not found")

    norms = db.scalars(
        select(MatrixNorm).where(
            and_(
                MatrixNorm.matrix_id == matrix_id,
                MatrixNorm.deleted_at.is_(None),
            )
        )
    ).all()

    total_articles = 0
    compliant = 0
    non_compliant = 0
    not_evaluated = 0

    for norm in norms:
        articles = db.scalars(
            select(ArticleCompliance).where(
                and_(
                    ArticleCompliance.matrix_norm_id == norm.id,
                    ArticleCompliance.deleted_at.is_(None),
                )
            )
        ).all()

        for art in articles:
            total_articles += 1
            if art.compliance_status == "compliant":
                compliant += 1
            elif art.compliance_status == "non_compliant":
                non_compliant += 1
            else:
                not_evaluated += 1

    pct = round((compliant / total_articles * 100), 1) if total_articles > 0 else 0.0

    return {
        "matrix_id": str(matrix_id),
        "period_year": matrix.period_year,
        "status": matrix.status,
        "total_norms": len(norms),
        "total_articles": total_articles,
        "compliant": compliant,
        "non_compliant": non_compliant,
        "not_evaluated": not_evaluated,
        "compliance_percentage": pct,
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
