"""El agente: responde con evidencia o no responde (SPEC-06)."""

from .grafo import Agente, EventoAgente, RespuestaAgente
from .revisor import Evaluacion, Revisor, RevisorModelo, RevisorNulo

__all__ = [
    "Agente",
    "EventoAgente",
    "RespuestaAgente",
    "Evaluacion",
    "Revisor",
    "RevisorModelo",
    "RevisorNulo",
]
