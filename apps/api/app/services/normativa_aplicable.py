"""Que normas le corresponden a una empresa segun su perfil (RF-19).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

Es el eslabon que faltaba: el sistema sabia que normas existen y sabia evaluar
un articulo, pero no sabia **cuales le tocan a esta empresa**.

## La distincion que hay que no perder

Una lista vacia tiene **dos causas opuestas**:

- El sector no tiene ninguna norma clasificada todavia → falta trabajo nuestro
- La empresa no tiene perfil declarado → falta un dato de ella

Ninguna de las dos significa "no tiene obligaciones". Por eso el resultado no es
una lista sino un objeto que **dice cual de los tres casos es**: mostrar una
lista vacia sin explicar por que le haria creer a una empresa que esta en regla.

## Que decide obligatoria y que recomendada

`norm_sectors.applicability_level`:

- `directa` → la debe cumplir
- `indirecta` y `referencial` → se le recomienda revisarla

No es una escala de importancia que alguien pueda reinterpretar: es la
distincion que pidio el negocio, y por eso el nivel no admite texto libre.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.catalog import LegalNorm, NormSector
from ..models.organization import Tenant

#: Niveles que vuelven obligatoria a una norma. El resto son recomendaciones.
NIVELES_OBLIGATORIOS = frozenset({"directa"})


@dataclass(frozen=True)
class NormaAplicable:
    """Una norma que le corresponde a la empresa, y por que le corresponde."""

    norm_id: UUID
    title: str
    norm_type: str
    norm_number: str | None
    sector_id: int
    applicability_level: str
    rationale: str | None

    @property
    def obligatoria(self) -> bool:
        return self.applicability_level in NIVELES_OBLIGATORIOS


@dataclass(frozen=True)
class NormativaAplicable:
    """El resultado del calculo, con el motivo cuando viene vacio."""

    #: 'con_normativa' | 'sector_sin_clasificar' | 'sin_perfil'
    estado: str
    obligatorias: list[NormaAplicable] = field(default_factory=list)
    recomendadas: list[NormaAplicable] = field(default_factory=list)
    sector_id: int | None = None

    @property
    def total(self) -> int:
        return len(self.obligatorias) + len(self.recomendadas)


def calcular(db: Session, tenant_id: UUID) -> NormativaAplicable:
    """Que normas le corresponden a esta empresa. **No escribe nada.**

    Calcular y aplicar son operaciones distintas a proposito: el negocio pidio
    "un check de normativas recomendadas", y un check es una revision humana
    antes de comprometer. Generar la matriz de golpe le daria a la empresa
    cientos de articulos que evaluar sin que nadie mirara si tienen sentido.
    """
    empresa = db.get(Tenant, tenant_id)
    if empresa is None or empresa.sector_id is None:
        # Sin sector no hay con que cruzar. Se distingue del caso siguiente
        # porque la accion que destraba cada uno es distinta: aca la hace la
        # empresa, alla la hacemos nosotros.
        return NormativaAplicable(estado="sin_perfil")

    filas = db.execute(
        select(NormSector, LegalNorm)
        .join(LegalNorm, LegalNorm.id == NormSector.norm_id)
        .where(
            NormSector.sector_id == empresa.sector_id,
            LegalNorm.deleted_at.is_(None),
        )
        .order_by(LegalNorm.title)
    ).all()

    if not filas:
        return NormativaAplicable(
            estado="sector_sin_clasificar", sector_id=empresa.sector_id
        )

    obligatorias: list[NormaAplicable] = []
    recomendadas: list[NormaAplicable] = []
    for clasificacion, norma in filas:
        item = NormaAplicable(
            norm_id=norma.id,
            title=norma.title,
            norm_type=norma.norm_type,
            norm_number=norma.norm_number,
            sector_id=clasificacion.sector_id,
            applicability_level=clasificacion.applicability_level,
            rationale=clasificacion.rationale,
        )
        (obligatorias if item.obligatoria else recomendadas).append(item)

    return NormativaAplicable(
        estado="con_normativa",
        obligatorias=obligatorias,
        recomendadas=recomendadas,
        sector_id=empresa.sector_id,
    )
