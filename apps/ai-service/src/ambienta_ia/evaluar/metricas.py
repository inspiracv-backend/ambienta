from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from datetime import date

from ..citas import normalizar_norma, numero_normal


@dataclass
class Caso:
    id: str
    pregunta: str
    norma: str | None = None  # "Ley 19.300"; se normaliza a "ley/19300"
    articulos_esperados: list[str] = field(default_factory=list)
    fecha: date | None = None
    debe_abstenerse: bool = False
    respuesta_referencia: str | None = None
    autor: str | None = None
    revisado_por: str | None = None

    @property
    def clave_norma(self) -> str | None:
        return normalizar_norma(self.norma) if self.norma else None

    @property
    def esperados(self) -> set[str]:
        return {numero_normal(a) or a for a in self.articulos_esperados}


def cargar_dataset(ruta: str | pathlib.Path) -> list[Caso]:
    casos = []
    for n, linea in enumerate(pathlib.Path(ruta).read_text(encoding="utf-8").splitlines(), start=1):
        if not linea.strip() or linea.lstrip().startswith("//"):
            continue
        datos = json.loads(linea)
        if datos.get("fecha"):
            datos["fecha"] = date.fromisoformat(datos["fecha"])
        try:
            casos.append(Caso(**datos))
        except TypeError as e:
            raise ValueError(f"Línea {n}: {e}") from e
    ids = [c.id for c in casos]
    if len(ids) != len(set(ids)):
        raise ValueError("Hay ids repetidos en el dataset.")
    return casos


def recall_en_k(esperados: set[str], recuperados: list[str], k: int) -> float:
    """De los que debían aparecer, cuántos aparecieron entre los primeros k."""
    if not esperados:
        return 1.0
    return len(set(recuperados[:k]) & esperados) / len(esperados)


def precision_en_k(esperados: set[str], recuperados: list[str], k: int) -> float:
    top = recuperados[:k]
    if not top:
        return 0.0
    return sum(1 for a in top if a in esperados) / len(top)


def mrr(esperados: set[str], recuperados: list[str]) -> float:
    """1 / posición del primer acierto. Distingue "estaba primero" de "estaba séptimo"."""
    for i, a in enumerate(recuperados, start=1):
        if a in esperados:
            return 1.0 / i
    return 0.0
