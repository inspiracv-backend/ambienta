"""Mantener la base de conocimiento igual al catálogo del backend (SPEC-04)."""

from .arbol import armar_ruta, elegir_vigente, fragmentar_norma
from .sincronizador import ResultadoSincronizacion, sincronizar

__all__ = [
    "armar_ruta",
    "elegir_vigente",
    "fragmentar_norma",
    "sincronizar",
    "ResultadoSincronizacion",
]
