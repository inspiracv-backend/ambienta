"""Invitar por correo a alguien de la empresa (#139, RF-03).

## Por que la invitacion la emite Clerk y no nosotros

La identidad la administra Clerk (ADR-006): nosotros no guardamos claves. Una
persona invitada necesita **poder crearse la cuenta**, y `openspec/changes/
integracion-clerk-auth/proposal.md` deja abierta la decision #4 —si se permite
signup publico— con la inclinacion a **deshabilitarlo**, porque si no cualquiera
podria crearse cuenta.

Con el signup cerrado, la invitacion de Clerk **es** el mecanismo: crea un enlace
de un solo uso ligado a ese correo y manda el mensaje desde un remitente ya
verificado.

La alternativa —mandar nuestro propio correo por Resend— hoy **no funcionaria**:
Resend no esta configurado (hace falta cuenta y dominio verificado, que es una
decision pendiente), mientras que `CLERK_SECRET_KEY` si lo esta. Un camino que
no puede ejecutarse no es una funcionalidad.

## El detalle que hace la diferencia entre entrar y no entrar

**La invitacion tiene que llevar `public_metadata` con el `tenant_id`.**

El claim de empresa sale de ahi: el JWT Template de Clerk lo inyecta, y sin el
la persona acepta la invitacion, se crea la cuenta, entra... y recibe
`403 sesion_sin_empresa` **en todo el sistema**. Clerk copia `public_metadata`
de la invitacion al usuario al aceptarla, asi que es el unico momento en que se
puede dejar puesto sin tocar la consola a mano.

Es exactamente el paso que CLAUDE.md describe como manual en local ("Clerk →
Users → Public metadata"). Aca deja de serlo.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.organization import Role, User
from .clave_local import ClerkNoDisponible, ErrorDeClaveLocal, _clerk
from .usuarios import fijar_roles

logger = logging.getLogger(__name__)

#: Estados en los que **no** se invita.
#:
#: A alguien activo ya le funciona su cuenta: reinvitarlo le manda un enlace que
#: no necesita y siembra la duda de si su acceso dejo de servir. A alguien
#: apagado, invitarlo seria devolverle el acceso por la puerta de atras, sin
#: pasar por la decision de reactivarlo.
NO_SE_INVITA = frozenset({"active", "blocked", "disabled"})


class ErrorDeInvitacion(Exception):
    """No corresponde invitar a esta persona, o Clerk no lo acepto."""


class NoCorrespondeInvitar(ErrorDeInvitacion):
    """Por el estado de la cuenta."""


class YaInvitado(ErrorDeInvitacion):
    """Clerk ya tiene una invitacion pendiente para ese correo."""


def invitar(usuario: User) -> dict[str, Any]:
    """Crea la invitacion en Clerk para esa persona.

    Devuelve lo que Clerk respondio. No escribe nada en nuestra base: el estado
    `invited` ya lo puso la creacion del usuario, y duplicar aca un "invitado
    el..." seria un segundo registro de la misma cosa que se desincroniza —
    Clerk ya sabe si la invitacion sigue pendiente.
    """
    if usuario.status in NO_SE_INVITA:
        raise NoCorrespondeInvitar(
            f"{usuario.full_name} esta en estado «{usuario.status}»: la "
            "invitacion es para quien todavia no tiene acceso."
        )

    if not usuario.email:
        raise NoCorrespondeInvitar(
            "Esa persona no tiene correo, asi que no hay a donde invitarla."
        )

    cuerpo: dict[str, Any] = {
        "email_address": usuario.email,
        # **Lo que decide si la persona podra trabajar.** Sin esto acepta,
        # entra, y recibe 403 en todo el sistema porque su sesion no declara
        # empresa. Clerk lo copia al usuario al aceptar la invitacion.
        "public_metadata": {"tenant_id": str(usuario.tenant_id)},
        # Que la reenvie si ya existe una pendiente en vez de fallar: quien
        # administra reintenta cuando la persona dice que no le llego, y un
        # error ahi se lee como que el sistema esta roto.
        "notify": True,
    }

    try:
        return _clerk("POST", "/invitations", cuerpo)
    except ErrorDeClaveLocal as exc:
        # Clerk devuelve 400/422 con su propio motivo. El mas comun es que ya
        # exista una invitacion para ese correo, y ese caso se distingue porque
        # se arregla distinto: no hay nada que corregir, ya esta invitada.
        texto = str(exc).lower()
        if "duplicate" in texto or "already" in texto:
            raise YaInvitado(
                f"Ya hay una invitacion pendiente para {usuario.email}. "
                "Revisa su bandeja o el correo no deseado."
            ) from None
        raise ErrorDeInvitacion(str(exc)) from None
    except ClerkNoDisponible:
        # Se deja subir tal cual: no es un problema del dato que se mando, y el
        # router lo traduce a 503. Tratarlo como un error de la peticion diria
        # que quien invita hizo algo mal.
        raise


def invitar_por_id(db: Session, user_id: UUID) -> tuple[User, dict[str, Any]]:
    """Busca a la persona con la sesion del tenant y la invita.

    Se lee con la sesion del tenant a proposito: si RLS no la ve, para esta
    empresa no existe, y el 404 llega antes de tocar Clerk.
    """
    usuario = db.get(User, user_id)
    if usuario is None or usuario.deleted_at is not None:
        raise NoCorrespondeInvitar("Esa persona no corresponde a esta empresa.")
    return usuario, invitar(usuario)


#: Los tipos de cuenta que se invitan desde una empresa. `platform_admin` y
#: `manager` no son personas de la empresa, y `guest` tiene su propio camino.
TIPOS_INVITABLES = frozenset({"internal", "tenant_admin"})


class RolNoDisponible(ErrorDeInvitacion):
    """El rol pedido no existe en esta empresa."""


def registrar_e_invitar(
    db: Session,
    tenant_id: UUID,
    *,
    full_name: str,
    email: str,
    user_type: str,
    department_id: UUID | None,
    role_code: str,
) -> tuple[User, dict[str, Any]]:
    """Crea a la persona con su rol y le manda la invitacion, **como un acto**.

    ## Por que no son dos llamadas

    La pantalla hacia `POST /users/` y nunca llamaba a `/invitacion`: la fila
    quedaba en `invited` y la persona **jamas recibia el correo**, mientras el
    aviso decia "Invitacion creada". Y separarlas en dos peticiones tampoco
    alcanza: si la segunda falla queda una fila que ocupa el correo —`email` es
    unico— y que nadie puede usar.

    ## El orden dentro de la transaccion (D4 de `credenciales-de-acceso`)

    Todo lo nuestro se escribe y se valida con `flush` **antes** de hablar con
    Clerk, y el `commit` lo hace quien llama **despues**. Si Clerk rechaza o no
    responde, la excepcion sube, no hay commit y no queda nada: ni fila ni rol.
    Si Clerk acepta y el commit fallara —ya validado todo, es lo improbable—
    queda una invitacion huerfana, que es basura visible en su consola y se
    repara sola por el webhook.

    **Sin rol no se invita.** Una persona sin rol recibe 403 en todo con la
    guarda conectada, y el sintoma no apunta a la causa.

    No confirma la transaccion: eso es de quien llama.
    """
    if user_type not in TIPOS_INVITABLES:
        raise NoCorrespondeInvitar(
            f"El tipo de cuenta «{user_type}» no se invita desde una empresa."
        )
    return crear_cuenta_e_invitar(
        db,
        tenant_id,
        full_name=full_name,
        email=email,
        user_type=user_type,
        department_id=department_id,
        role_code=role_code,
    )


def crear_cuenta_e_invitar(
    db: Session,
    tenant_id: UUID,
    *,
    full_name: str,
    email: str,
    user_type: str,
    department_id: UUID | None,
    role_code: str,
) -> tuple[User, dict[str, Any]]:
    """El acto en si, sin mirar si el tipo se invita desde una empresa.

    Separado de `registrar_e_invitar` para el primer Admin Global
    (`tareas/crear_admin_global.py`): es un `platform_admin`, que ninguna empresa
    puede invitar por la API, pero se crea con exactamente el mismo orden —fila
    y rol con `flush`, Clerk al final, commit de quien llama—.
    """
    rol = db.scalar(
        select(Role).where(
            Role.tenant_id == tenant_id,
            Role.code == role_code,
            Role.deleted_at.is_(None),
        )
    )
    if rol is None:
        raise RolNoDisponible(f"La empresa no tiene el rol «{role_code}».")

    usuario = User(
        tenant_id=tenant_id,
        department_id=department_id,
        email=email,
        full_name=full_name,
        user_type=user_type,
        status="invited",
    )
    db.add(usuario)
    db.flush()
    fijar_roles(db, usuario, tenant_id, [rol.id])
    db.flush()

    return usuario, invitar(usuario)
