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

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.organization import User
from .permisos import permisos_efectivos

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
