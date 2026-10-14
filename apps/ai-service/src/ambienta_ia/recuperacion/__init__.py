"""Buscar en la norma: exacta, por palabras, semántica y a una fecha (SPEC-05)."""

from .buscar import Recuperador
from .fusion import fusionar
from .reordenar import Reordenador, ReordenadorModelo
from .tipos import Cita, Recuperacion, Resultado

__all__ = ["Recuperador", "Recuperacion", "Resultado", "Cita", "fusionar", "Reordenador", "ReordenadorModelo"]
