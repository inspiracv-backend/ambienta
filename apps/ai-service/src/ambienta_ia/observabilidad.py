"""
Logs en JSON y una traza por consulta (SPEC-09).

La traza es lo que permite explicar una respuesta después: qué se preguntó, qué se buscó, con
qué similitud, qué herramientas se llamaron, qué se citó y cuánto costó. Nunca lleva el token ni
el texto de documentos privados.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

log = logging.getLogger("ambienta_ia")


class FormatoJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        datos: dict[str, Any] = {
            "ts": round(record.created, 3),
            "nivel": record.levelname,
            "evento": record.getMessage(),
        }
        extra = getattr(record, "datos", None)
        if isinstance(extra, dict):
            datos.update(extra)
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False, default=str)


def configurar_logs(nivel: str = "INFO") -> None:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormatoJSON())
    raiz = logging.getLogger("ambienta_ia")
    raiz.handlers[:] = [manejador]
    raiz.setLevel(nivel)
    raiz.propagate = False


def evento(nombre: str, **datos: Any) -> None:
    log.info(nombre, extra={"datos": datos})


def aviso(nombre: str, **datos: Any) -> None:
    log.warning(nombre, extra={"datos": datos})


@dataclass
class LlamadaHerramienta:
    nombre: str
    argumentos: dict[str, Any]
    duracion_ms: int
    resultado: str  # "evidencia" | "sin_resultados" | "error" | "datos"
    detalle: str | None = None


@dataclass
class Traza:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    tenant_id: str | None = None
    conversation_id: str | None = None
    pregunta: str = ""
    fecha: str | None = None
    modo_busqueda: str | None = None
    fragmentos: list[dict[str, Any]] = field(default_factory=list)
    herramientas: list[LlamadaHerramienta] = field(default_factory=list)
    modelo: str | None = None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    revisiones: list[dict[str, Any]] = field(default_factory=list)
    se_abstuvo: bool | None = None
    motivo_abstencion: str | None = None
    citas: list[str] = field(default_factory=list)
    guardado: bool | None = None
    error: str | None = None
    vacios_inesperados: list[dict[str, Any]] = field(default_factory=list)
    _inicio: float = field(default_factory=time.monotonic, repr=False)
    latencia_ms: int | None = None

    def cerrar(self) -> None:
        self.latencia_ms = int((time.monotonic() - self._inicio) * 1000)

    def como_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("_inicio", None)
        return d


class Exportador(Protocol):
    def exportar(self, traza: Traza) -> None: ...


class ExportadorLog:
    def exportar(self, traza: Traza) -> None:
        log.info("traza", extra={"datos": traza.como_dict()})


class ExportadorMemoria:
    """Para pruebas y para inspeccionar las últimas consultas en desarrollo."""

    def __init__(self, maximo: int = 200):
        self.trazas: deque[Traza] = deque(maxlen=maximo)

    def exportar(self, traza: Traza) -> None:
        self.trazas.append(traza)


class ExportadorCompuesto:
    def __init__(self, *exportadores: Exportador):
        self._exportadores = exportadores

    def exportar(self, traza: Traza) -> None:
        for e in self._exportadores:
            try:
                e.exportar(traza)
            except Exception:  # una traza que no se exporta no puede tumbar la consulta
                log.exception("exportar_traza_fallo")
