"""Resolucion del permiso efectivo de un usuario (RF-08, RF-12).

Spec: `openspec/changes/sistema-actores-roles-rbac/specs/rbac/spec.md`.

El permiso efectivo es la union de lo que conceden los roles vigentes del
usuario con sus concesiones individuales, y **una denegacion explicita gana
sobre cualquier concesion**. Ese orden no es un detalle de implementacion: es
lo que permite quitarle *un* permiso a alguien sin sacarlo del rol ni inventar
un rol de excepcion por cada caso.

## Por que se resuelve aca y no en la base

Podria hacerse con una vista. Se hace en Python porque la regla de precedencia
—denegacion gana— es una decision de negocio que conviene tener escrita y
probada en un solo lugar, no repartida en una vista que despues alguien
optimiza sin leer por que estaba asi.

## Lo que esto NO hace

No filtra filas. El aislamiento entre empresas lo sigue garantizando Row Level
Security, que es la unica barrera (CLAUDE.md §4). Esto decide **si la operacion
se permite**, no **que filas se ven**: son dos preguntas distintas y confundirlas
llevaria a creer que un permiso alcanza para proteger datos de otra empresa.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models.organization import (
    Permission,
    Role,
    RolePermission,
    UserPermission,
    UserRole,
)


def _ahora():
    """El reloj de **la base**, no el de la aplicacion.

    `user_roles.valid_from` tiene `now()` por defecto, o sea que lo escribe
    Postgres. Comparar esa columna contra `datetime.now()` de Python mezcla dos
    relojes en una sola comparacion, y basta un desfase de milisegundos para
    que un rol recien asignado se lea como **todavia no vigente**: la persona
    entra, se le da el rol, y el sistema le dice que no tiene permiso.

    No es teorico. Pasa en esta maquina: el 27-ago tres pruebas de este modulo
    fallaron de golpe y volvieron a pasar solas minutos despues, sin que nadie
    tocara nada. Las tres eran las unicas que asignan un rol y comprueban en
    seguida que rige; las que afirman lo contrario —rol vencido no concede—
    siguieron pasando, que es exactamente la firma de un `valid_from` que quedo
    en el futuro. En produccion la API y la base son maquinas distintas, donde
    el desfase es la norma y no la excepcion.

    Con `func.now()` la comparacion la resuelve Postgres contra su propio
    reloj, que es el mismo que escribio el valor. Un reloj, una comparacion.
    """
    return func.now()


def permisos_de_roles(db: Session, user_id: UUID) -> set[str]:
    """Lo que conceden los roles **vigentes** del usuario.

    Vigente es `valid_from <= ahora` y (`valid_to` nula o futura). Un rol
    vencido no concede nada: es la diferencia entre "fue encargado" y "es
    encargado", y sin el filtro alguien conserva permisos despues de que se le
    retiraron.
    """
    ahora = _ahora()
    filas = db.execute(
        select(Permission.code, RolePermission.granted)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(
            UserRole.user_id == user_id,
            UserRole.valid_from <= ahora,
            or_(UserRole.valid_to.is_(None), UserRole.valid_to > ahora),
        )
    ).all()
    # `role_permissions.granted` puede ser false: es una fila que dice
    # explicitamente que ese rol NO da ese permiso. Se ignora al unir, en vez
    # de tratarla como concesion.
    return {codigo for codigo, concedido in filas if concedido}


def roles_vigentes(db: Session, user_id: UUID) -> list[str]:
    """Los codigos de rol que la persona tiene **hoy**.

    Misma regla de vigencia que `permisos_de_roles`, y por el mismo motivo: un
    rol vencido no es un rol. Se comparte el criterio en vez de repetirlo porque
    dos definiciones de "vigente" se desincronizan sin que nada falle — una
    diria que la persona es encargada y la otra le negaria los permisos.

    **Es una etiqueta, no una regla.** Para decidir si una accion se permite
    esta `permisos_efectivos`, que ademas aplica las excepciones individuales.
    Ramificar sobre el rol se salta la denegacion individual, que es justo el
    mecanismo para quitarle algo a alguien sin sacarlo del rol.
    """
    ahora = _ahora()
    filas = db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.valid_from <= ahora,
            or_(UserRole.valid_to.is_(None), UserRole.valid_to > ahora),
        )
    ).all()
    return sorted({codigo for (codigo,) in filas})


def excepciones_del_usuario(db: Session, user_id: UUID) -> tuple[set[str], set[str]]:
    """Concesiones y denegaciones asignadas a esta persona en particular.

    Devuelve `(concedidas, denegadas)` por separado y no un solo conjunto,
    porque las denegaciones tienen precedencia y mezclarlas obligaria a
    recalcular el orden en cada sitio que las use.
    """
    filas = db.execute(
        select(Permission.code, UserPermission.granted)
        .join(UserPermission, UserPermission.permission_id == Permission.id)
        .where(UserPermission.user_id == user_id)
    ).all()
    concedidas = {codigo for codigo, concedido in filas if concedido}
    denegadas = {codigo for codigo, concedido in filas if not concedido}
    return concedidas, denegadas


def permisos_efectivos(db: Session, user_id: UUID) -> set[str]:
    """Que puede hacer esta persona, todo junto.

    Union de roles y concesiones individuales, menos las denegaciones.

    **El orden de las dos operaciones no cambia el resultado**, y conviene
    decirlo para que nadie lo "arregle": la clave primaria de
    `user_permissions` es `(user_id, permission_id)`, asi que un permiso no
    puede estar concedido y denegado a la vez para la misma persona. Los
    conjuntos son disjuntos por construccion.

    Lo que si importa —y esta probado— es que la denegacion **le gana a lo que
    concede el rol**. Esa es la propiedad util: permite quitarle un permiso a
    alguien sin sacarlo del rol.
    """
    concedidas, denegadas = excepciones_del_usuario(db, user_id)
    return (permisos_de_roles(db, user_id) | concedidas) - denegadas


def tiene_permiso(db: Session, user_id: UUID, codigo: str) -> bool:
    """Si esta persona puede hacer esa accion.

    Se resuelve el conjunto entero en vez de consultar el permiso suelto: son
    dos consultas cortas contra tablas chicas, y evita que la regla de
    precedencia quede escrita dos veces.
    """
    return codigo in permisos_efectivos(db, user_id)


def alcance_del_usuario(db: Session, user_id: UUID) -> tuple[set[UUID], set[UUID]]:
    """A que instalaciones y departamentos esta acotado, si lo esta.

    Devuelve `(instalaciones, departamentos)`. **Un conjunto vacio significa
    "sin acotar", no "ninguno"** — es la diferencia entre un encargado de toda
    la empresa y uno que no tiene acceso a nada, y confundirlas dejaria a los
    administradores sin ver nada.

    Solo cuentan los roles vigentes, por la misma razon que en
    `permisos_de_roles`.
    """
    ahora = _ahora()
    filas = db.execute(
        select(UserRole.facility_id, UserRole.department_id).where(
            UserRole.user_id == user_id,
            UserRole.valid_from <= ahora,
            or_(UserRole.valid_to.is_(None), UserRole.valid_to > ahora),
        )
    ).all()

    # Si CUALQUIER rol vigente viene sin acotar, la persona no esta acotada:
    # el rol mas amplio manda. Acotar por la interseccion dejaria a alguien con
    # dos roles —uno global y uno de planta— viendo solo esa planta, que es lo
    # contrario de lo que significa tener ademas un rol global.
    if any(f is None and d is None for f, d in filas):
        return set(), set()

    instalaciones = {f for f, _ in filas if f is not None}
    departamentos = {d for _, d in filas if d is not None}
    return instalaciones, departamentos
