from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

Origen = Literal["exacta", "palabras", "semantica", "en_vivo"]


@dataclass(frozen=True)
class Cita:
    """
    La referencia verificable. Es también lo que se guarda en `citations` del mensaje en el
    backend: los campos `norma`, `articulo` y `texto` coinciden con el ejemplo del handoff §7.
    """

    norma: str
    articulo: str | None
    ruta: str
    texto: str
    norm_id: UUID
    article_id: UUID | None
    norm_version_id: UUID | None
    official_url: str | None = None
    origen: Literal["catalogo", "normativa_propia", "documento"] = "catalogo"

    def como_dict(self) -> dict[str, Any]:
        return {
            "norma": self.norma,
            "articulo": self.articulo,
            "texto": self.texto,
            "ruta": self.ruta,
            "norm_id": str(self.norm_id),
            "article_id": str(self.article_id) if self.article_id else None,
            "norm_version_id": str(self.norm_version_id) if self.norm_version_id else None,
            "official_url": self.official_url,
            "origen": self.origen,
        }

    @property
    def etiqueta(self) -> str:
        return f"{self.norma}, artículo {self.articulo}" if self.articulo else self.norma


@dataclass
class Resultado:
    clave: str  # identidad para fusionar: article_id:parte
    cita: Cita
    similitud: float | None  # coseno contra la pregunta; es la que decide la evidencia
    puntaje: float = 0.0  # orden final (fusión); no decide nada
    origen: set[Origen] = field(default_factory=set)


@dataclass
class Recuperacion:
    resultados: list[Resultado]
    modo: Literal["exacta", "combinada", "historica", "ninguna"]
    hay_evidencia: bool
    mejor_similitud: float | None
