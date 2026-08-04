"""Lógica de negocio para ISO 14001 — significancia de aspectos ambientales."""
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from ..models.iso14001 import EnvironmentalAspect


SIGNIFICANCE_THRESHOLD = 15


def calculate_significance(aspect: EnvironmentalAspect) -> tuple[int, bool]:
    score = (
        (aspect.frequency_score or 0)
        * (aspect.severity_score or 0)
        + (aspect.detection_score or 0)
    )
    return score, score >= SIGNIFICANCE_THRESHOLD


def evaluate_aspect(
    db: Session,
    aspect_id: UUID,
    frequency: int,
    severity: int,
    detection: int,
) -> EnvironmentalAspect:
    aspect = db.get(EnvironmentalAspect, aspect_id)
    if not aspect:
        raise ValueError("Environmental aspect not found")

    for name, val in [("frequency", frequency), ("severity", severity), ("detection", detection)]:
        if not (1 <= val <= 5):
            raise ValueError(f"{name} must be between 1 and 5")

    aspect.frequency_score = frequency
    aspect.severity_score = severity
    aspect.detection_score = detection

    score, significant = calculate_significance(aspect)
    aspect.significance = "significant" if significant else "not_significant"

    db.flush()
    db.refresh(aspect)
    return aspect


def get_significant_aspects(db: Session, tenant_id: UUID) -> list[EnvironmentalAspect]:
    stmt = (
        select(EnvironmentalAspect)
        .where(
            and_(
                EnvironmentalAspect.tenant_id == tenant_id,
                EnvironmentalAspect.significance == "significant",
                EnvironmentalAspect.deleted_at.is_(None),
            )
        )
    )
    return list(db.scalars(stmt).all())
