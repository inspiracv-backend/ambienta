"""
Todo lo que el AI Service sabe del backend de Ambienta vive en este paquete (SPEC-01).

Si el contrato del backend cambia, se toca `modelos.py` y `cliente.py`, y nada más.
"""

from .cliente import ClienteBackend
from .errores import (
    AlmacenamientoNoConfigurado,
    BackendCaido,
    ErrorBackend,
    EstadoNoAdmite,
    NoEncontrado,
    PeticionInvalida,
    SinAutenticar,
    SinPermiso,
)

__all__ = [
    "ClienteBackend",
    "ErrorBackend",
    "SinAutenticar",
    "SinPermiso",
    "NoEncontrado",
    "PeticionInvalida",
    "EstadoNoAdmite",
    "AlmacenamientoNoConfigurado",
    "BackendCaido",
]
