"""Cuanta normativa falta clasificar, y donde (RF-19).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

## Para que existe esto

Todo el mecanismo de normativa aplicable descansa en `norm_sectors`: una norma
sin clasificar no le llega a ninguna empresa. Como la tabla nace vacia, el
sistema entero **funciona y no propone nada**, y la unica senal es que la matriz
responde `sector_sin_clasificar` — un estado que se lee como un error tecnico
cuando en realidad es trabajo pendiente de una persona.

Este servicio convierte ese silencio en un numero: cuantas normas hay, cuantas
no las miro nadie, y como esta cada sector. Es lo que hace que el trabajo se vea
en vez de descubrirse cuando un cliente pregunta por que su matriz esta vacia.

## "Sin clasificar" es no tener ninguna fila, no tener pocas

Una norma con una sola clasificacion ya fue revisada: alguien decidio a que
sector aplica. Contarla como pendiente porque no cubre los 21 sectores CIIU
inflaria la cifra hasta volverla inutil — casi ninguna ley aplica a todos.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.catalog import LegalNorm, NormSector, Sector


@dataclass
class CoberturaDeSector:
    sector_id: int
    codigo: str
    nombre: str
    #: Normas obligatorias para este sector: `applicability_level = 'directa'`.
    directas: int
    #: `indirecta` + `referencial`. Se proponen como recomendadas, no obligan.
    recomendadas: int

    @property
    def total(self) -> int:
        return self.directas + self.recomendadas


@dataclass
class Cobertura:
    normas_totales: int
    #: Normas sin **ninguna** fila en `norm_sectors`. El trabajo pendiente.
    normas_sin_clasificar: int
    por_sector: list[CoberturaDeSector]

    @property
    def sectores_sin_normativa(self) -> int:
        """Sectores donde una empresa entraria y no recibiria nada."""
        return sum(1 for s in self.por_sector if s.total == 0)


def calcular(db: Session) -> Cobertura:
    """El estado de la clasificacion normativa, entero.

    Se listan **todos** los sectores, incluidos los que tienen cero normas. Son
    justamente los que importan: un sector ausente de la lista se lee como "no
    existe", y uno en cero se lee como "aca falta trabajo", que es lo cierto.
    """
    normas_totales = (
        db.execute(
            select(func.count(LegalNorm.id)).where(LegalNorm.deleted_at.is_(None))
        ).scalar_one()
        or 0
    )

    clasificadas = (
        db.execute(select(func.count(func.distinct(NormSector.norm_id)))).scalar_one() or 0
    )

    conteos = {
        sector_id: (directas or 0, recomendadas or 0)
        for sector_id, directas, recomendadas in db.execute(
            select(
                NormSector.sector_id,
                func.count(NormSector.norm_id).filter(
                    NormSector.applicability_level == "directa"
                ),
                func.count(NormSector.norm_id).filter(
                    NormSector.applicability_level != "directa"
                ),
            )
            .join(LegalNorm, LegalNorm.id == NormSector.norm_id)
            .where(LegalNorm.deleted_at.is_(None))
            .group_by(NormSector.sector_id)
        ).all()
    }

    sectores = db.execute(
        select(Sector.id, Sector.code, Sector.name).order_by(Sector.code)
    ).all()

    return Cobertura(
        normas_totales=normas_totales,
        # Puede dar negativo si una norma clasificada se borro logicamente. Se
        # acota en cero: mostrar "-2 sin clasificar" es peor que redondear.
        normas_sin_clasificar=max(0, normas_totales - clasificadas),
        por_sector=[
            CoberturaDeSector(
                sector_id=sid,
                codigo=codigo,
                nombre=nombre,
                directas=conteos.get(sid, (0, 0))[0],
                recomendadas=conteos.get(sid, (0, 0))[1],
            )
            for sid, codigo, nombre in sectores
        ],
    )
