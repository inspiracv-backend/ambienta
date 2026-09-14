"""Asignacion de roles a personas (#140, RF-08)."""
from uuid import UUID

from pydantic import BaseModel, Field


class FijarRoles(BaseModel):
    """El estado final, no una adicion.

    Una lista vacia es legitima y significa **sin ningun rol**: la persona
    queda sin permisos. No se prohibe porque es como se retira el acceso de
    alguien sin sacarlo de la nomina; lo que si se rechaza es que ese alguien
    fuera la unica persona que podia administrar usuarios.
    """

    role_ids: list[UUID] = Field(default_factory=list)


class RolesDelUsuario(BaseModel):
    user_id: UUID
    role_ids: list[UUID]
    #: Los codigos (`admin_empresa`, `encargado_ambiental`, ...). Van al lado de
    #: los ids porque una pantalla que solo tenga ids tendria que pedir el
    #: catalogo entero para poder escribir un nombre.
    codigos: list[str]


class ResultadoDeRoles(RolesDelUsuario):
    #: Que cambio: roles asignados, retirados o reabiertos. Se devuelve para
    #: que la pantalla lo pueda decir, en vez de que la persona lo deduzca
    #: comparando antes y despues.
    efectos: list[str] = Field(default_factory=list)


class FijarAlcance(BaseModel):
    """A que planta queda acotada una persona.

    **`facility_id` es obligatorio aunque admita `null`.** `null` significa
    "todas las plantas", que es ampliar el acceso: un cuerpo vacio no puede
    hacerlo por omision.
    """

    facility_id: UUID | None


class AlcanceDelUsuario(BaseModel):
    user_id: UUID
    #: Vacia = **sin acotar**, ve todas las plantas. Es una lista y no un solo
    #: id porque SQL a mano pudo dejar roles en plantas distintas, y la pantalla
    #: tiene que poder decirlo en vez de mostrar solo una.
    facility_ids: list[UUID]
