"""Las dos formas de dejar una empresa sin quien la administre (#141, RF-08).

Desactivar a una persona parece una edicion de un campo, y es la operacion que
puede dejar a una empresa **sin ningun camino de vuelta**: si se apaga a quien
administra usuarios, no queda nadie que pueda volver a encenderlo, y la unica
salida es soporte tocando la base a mano.

Hay dos maneras distintas de llegar ahi, y **no se cubren con la misma regla**:

| Camino | Que lo evita | Se puede comprobar sin saber quien pide |
|---|---|---|
| Me apago a mi mismo | `es_uno_mismo` | **No**: hace falta identidad |
| Apago al ultimo que administra | `ultimo_que_administra` | **Si** |

La segunda es la que de verdad rompe la empresa, y por suerte es la que no
depende de saber quien hace la peticion — que importa porque **sin Clerk
configurado la API no conoce la identidad del usuario**: `CurrentUser.user_id`
llega vacio a proposito. Una guarda que dependiera solo de la identidad estaria
apagada en desarrollo sin que nada lo dijera, y quien la probara ahi concluiria
que funciona.

## Quien cuenta como "administrador"

No el que se llama `admin_empresa`: los roles son configurables por empresa
(#78 hizo lo mismo con las etapas del CRM), asi que un nombre no es una
garantia. Lo que importa es **quien conserva el permiso de administrar
usuarios**, que es la capacidad concreta que se perderia. Por eso se pregunta
por `user.write` con los permisos efectivos, que ya aplican rol **y** excepcion
individual, con la denegacion ganando.
"""
from __future__ import annotations

from uuid import UUID

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models.organization import User, UserRole
from .permisos import permisos_efectivos, permisos_si_tuviera_estos_roles

#: Poder volver a encender a alguien. Si nadie lo tiene, la empresa queda
#: administrable solo desde la base.
PERMISO_QUE_NO_SE_PUEDE_PERDER = "user.write"

#: Estados en los que la persona **no puede entrar**. `invited` no esta: es
#: alguien que todavia no acepto, no alguien a quien se le quito el acceso.
APAGADOS = frozenset({"blocked", "disabled"})


class ErrorDeUsuarios(Exception):
    """La operacion dejaria a la empresa en un estado del que no se vuelve."""


class NoPuedeDesactivarseSolo(ErrorDeUsuarios):
    """Quitarse el propio acceso deja fuera a quien esta trabajando."""


class UltimoQueAdministra(ErrorDeUsuarios):
    """No queda nadie que pueda volver a encender a nadie."""


def esta_activo(usuario: User) -> bool:
    return usuario.status not in APAGADOS and usuario.deleted_at is None


def es_uno_mismo(db: Session, usuario: User, clerk_id: str | None) -> bool:
    """Si la persona que pide la operacion es la misma que la sufre.

    Se compara por `clerk_id` y **no por el UUID interno**, porque lo unico que
    trae el token es el `sub` de Clerk. Un `clerk_id` vacio —que es lo que llega
    sin Clerk configurado— no identifica a nadie: devuelve `False`, y por eso
    esta regla no se puede sostener sola. La que sostiene el sistema es
    `ultimo_que_administra`.
    """
    if not clerk_id:
        return False
    return usuario.clerk_id == clerk_id


def ultimo_que_administra(db: Session, usuario: User, tenant_id: UUID) -> bool:
    """Si apagar a esta persona deja a la empresa sin quien administre usuarios.

    Se recorren los usuarios activos de la empresa y se pregunta por sus
    permisos efectivos. Son pocos por empresa, y la alternativa —deducirlo del
    nombre del rol— es justamente lo que falla cuando una empresa renombra o
    reconfigura sus roles.
    """
    if not tiene_el_permiso(db, usuario):
        # Quien no puede administrar usuarios no es el ultimo que puede.
        return False

    otros = db.scalars(
        select(User).where(
            User.tenant_id == tenant_id,
            User.id != usuario.id,
            User.deleted_at.is_(None),
        )
    ).all()

    for otro in otros:
        if esta_activo(otro) and tiene_el_permiso(db, otro):
            return False
    return True


def tiene_el_permiso(db: Session, usuario: User) -> bool:
    return PERMISO_QUE_NO_SE_PUEDE_PERDER in permisos_efectivos(db, usuario.id)


def validar_desactivacion(
    db: Session, usuario: User, tenant_id: UUID, *, clerk_id: str | None
) -> None:
    """Las dos guardas, en el orden en que ayudan mas.

    Primero la de uno mismo: cuando aplica, el mensaje puede decir exactamente
    que hacer (que lo haga otra persona). La del ultimo administrador es mas
    general pero su salida es mas laboriosa, asi que se deja para cuando la
    primera no explique el rechazo.
    """
    if es_uno_mismo(db, usuario, clerk_id):
        raise NoPuedeDesactivarseSolo(
            "No puedes desactivar tu propia cuenta: quedarias fuera del sistema "
            "en el acto. Pidele a otra persona que administre usuarios que lo "
            "haga por ti."
        )

    if ultimo_que_administra(db, usuario, tenant_id):
        raise UltimoQueAdministra(
            f"{usuario.full_name} es la unica persona activa que puede "
            "administrar usuarios. Desactivarla dejaria a la empresa sin nadie "
            "que pueda volver a dar acceso. Asignale antes ese permiso a "
            "alguien mas."
        )


def desactiva(anterior: str, nuevo: str | None) -> bool:
    """Si un cambio de estado apaga a alguien que estaba encendido.

    Se mira la **transicion** y no el estado destino: volver a guardar
    `disabled` sobre alguien que ya estaba desactivado no apaga a nadie, y
    rechazarlo convertiria una edicion inocua —cambiarle el departamento a una
    persona ya inactiva— en un 409 inexplicable.
    """
    if nuevo is None:
        return False
    return anterior not in APAGADOS and nuevo in APAGADOS


# ── Cambiar de rol (#140) ─────────────────────────────────────────────────


class SinAdministradorTrasElCambio(ErrorDeUsuarios):
    """El cambio de roles deja a la empresa sin quien administre usuarios."""


def _ahora(db: Session) -> datetime:
    """El reloj de **la base**, no el de la aplicacion.

    `permisos.py` compara la vigencia contra `now()` de Postgres, y dentro de
    una transaccion `now()` queda **congelado en el instante de apertura**. Con
    el reloj de Python —siempre posterior— un rol retirado quedaba con
    `valid_to` en el "futuro" respecto de esa comparacion y **seguia
    concediendo permisos**.

    Es la misma trampa de los dos relojes que ya costo tiempo en
    `services/permisos.py`. Un reloj, una comparacion.
    """
    return db.scalar(select(func.now()))


def roles_vigentes_de(db: Session, user_id: UUID) -> list[UserRole]:
    """Las asignaciones que rigen hoy. Un rol vencido no es un rol."""
    ahora = _ahora(db)
    return list(
        db.scalars(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.valid_from <= ahora,
                or_(UserRole.valid_to.is_(None), UserRole.valid_to > ahora),
            )
        ).all()
    )


def validar_cambio_de_roles(
    db: Session, usuario: User, tenant_id: UUID, role_ids: list[UUID]
) -> None:
    """Que cambiar de rol no sea otra forma de dejar a la empresa bloqueada.

    Es el mismo dano que desactivar al ultimo administrador (#141) por otra
    puerta: quitarle a la unica persona que puede administrar usuarios el rol
    que se lo daba deja a la empresa igual de trabada, y sin que nadie haya
    "desactivado" a nadie.

    Se comprueba **antes** de escribir, con `permisos_si_tuviera_estos_roles`.
    La alternativa —guardar y volver a preguntar— tiene que deshacer el cambio
    cuando sale mal, y ese camino solo se ejercita en el caso que justamente
    nadie prueba.
    """
    conserva = PERMISO_QUE_NO_SE_PUEDE_PERDER in permisos_si_tuviera_estos_roles(
        db, usuario.id, role_ids
    )
    if conserva:
        return

    # Deja de poder administrar. Solo importa si era el ultimo que podia.
    if ultimo_que_administra(db, usuario, tenant_id):
        raise SinAdministradorTrasElCambio(
            f"{usuario.full_name} es la unica persona activa que puede "
            "administrar usuarios. Con este rol dejaria de poder hacerlo y "
            "nadie quedaria para volver a dar acceso. Asignale antes ese "
            "permiso a alguien mas."
        )


def fijar_roles(
    db: Session, usuario: User, tenant_id: UUID, role_ids: list[UUID]
) -> list[str]:
    """Deja a la persona exactamente con esos roles, y dice que cambio.

    **Los roles que se quitan no se borran: se vencen** (`valid_to = ahora`).
    La clave primaria es `(user_id, role_id)`, asi que una asignacion retirada y
    vuelta a dar es la **misma fila** reabierta — el esquema no puede guardar
    dos periodos del mismo par. El historial de quien tuvo que rol y cuando vive
    en `audit_log`, que el observador del `flush` escribe solo porque esto pasa
    por la ORM.

    Borrar la fila en vez de vencerla perderia incluso el ultimo periodo, y con
    el la unica pista de que alguien tuvo ese rol.
    """
    ahora = _ahora(db)
    deseados = set(role_ids)
    efectos: list[str] = []

    existentes = {
        fila.role_id: fila
        for fila in db.scalars(
            select(UserRole).where(UserRole.user_id == usuario.id)
        ).all()
    }

    for role_id, fila in existentes.items():
        vigente = fila.valid_to is None or fila.valid_to > ahora
        if role_id in deseados and not vigente:
            # Se le vuelve a dar un rol que tuvo: se reabre la misma fila.
            fila.valid_from = ahora
            fila.valid_to = None
            efectos.append("se reasigno un rol que tuvo antes")
        elif role_id not in deseados and vigente:
            if fila.valid_from >= ahora:
                # Se asigno y se retiro **en la misma transaccion**: no hay
                # periodo que registrar. `ck_user_roles_vigencia` exige
                # `valid_to > valid_from`, y cualquier valor que lo cumpla
                # quedaria en el futuro respecto de `now()` — o sea, el rol
                # seguiria vigente. Un rol que nunca se vio desde fuera no
                # tiene historia: se borra.
                db.delete(fila)
            else:
                fila.valid_to = ahora
            efectos.append("se retiro un rol")

    for role_id in deseados - set(existentes):
        db.add(
            UserRole(
                user_id=usuario.id,
                role_id=role_id,
                tenant_id=tenant_id,
                valid_from=ahora,
            )
        )
        efectos.append("se asigno un rol nuevo")

    db.flush()
    return efectos
