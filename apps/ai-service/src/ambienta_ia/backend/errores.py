"""
Errores del backend traducidos, para que nadie fuera de este paquete mire códigos HTTP.

Un 404 o un 422 no dicen si el recurso es de otra empresa: el backend no lo distingue a
propósito (handoff §3), y acá tampoco se intenta adivinar.
"""

from __future__ import annotations

import re


class ErrorBackend(Exception):
    def __init__(self, detalle: str = "", estado: int | None = None):
        super().__init__(detalle)
        self.detalle = detalle
        self.estado = estado


class SinAutenticar(ErrorBackend):
    """401: falta el token, o falta X-Tenant-Id en modo desarrollo."""


class SinPermiso(ErrorBackend):
    """403: token válido, falta un permiso. El backend lo nombra en el mensaje."""

    @property
    def permiso(self) -> str | None:
        m = re.search(r"permiso\s+([\w.]+?)\.?$", self.detalle.strip())
        return m.group(1) if m else None


class NoEncontrado(ErrorBackend):
    """404: no existe, o no es de esta empresa."""


class PeticionInvalida(ErrorBackend):
    """422: el cuerpo está mal, o un id del cuerpo no es de esta empresa."""


class EstadoNoAdmite(ErrorBackend):
    """409: la operación es legítima pero el recurso no la admite en su estado."""


class AlmacenamientoNoConfigurado(ErrorBackend):
    """503 en descarga: es configuración, no una caída. No se reintenta."""


class BackendCaido(ErrorBackend):
    """5xx o red, después de agotar los reintentos."""
