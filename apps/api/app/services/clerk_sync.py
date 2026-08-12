"""Sincronizacion de usuarios desde Clerk hacia nuestra base.

Clerk es la fuente de verdad de la identidad (quien es, con que email entra);
nuestra base lo es de todo lo demas (a que tenant pertenece, que puede hacer,
que registro. Este modulo traduce eventos de Clerk a filas de `users` y nada
mas: no decide permisos ni crea tenants.

Separado del router a proposito, para poder probar la logica sin fabricar
firmas HTTP.

Spec: openspec/changes/integracion-clerk-auth/design.md §2.4.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.organization import User

logger = logging.getLogger(__name__)

# Clerk manda decenas de tipos de evento. Solo estos tres cambian algo aca.
EVENTOS_SOPORTADOS = ("user.created", "user.updated", "user.deleted")

# `users.user_type` de nuestro CHECK. Lo que venga en publicMetadata.role se
# valida contra esto: un rol inventado desde el dashboard de Clerk no puede
# entrar a la base.
TIPOS_VALIDOS = ("platform_admin", "tenant_admin", "internal", "guest", "manager")
TIPO_POR_DEFECTO = "internal"


class DatosDeClerkInvalidos(ValueError):
    """El evento venia firmado pero no trae lo minimo para actuar."""


def _email(data: dict) -> str:
    """El email primario del usuario.

    Clerk manda una lista y marca cual es el primario con `primary_email_address_id`.
    Tomar el primero del arreglo funciona casi siempre y falla justo cuando el
    usuario tiene dos correos, que es cuando importa.
    """
    correos = data.get("email_addresses") or []
    if not correos:
        raise DatosDeClerkInvalidos("el usuario no trae ninguna direccion de correo")

    primario_id = data.get("primary_email_address_id")
    for correo in correos:
        if primario_id and correo.get("id") == primario_id:
            return str(correo["email_address"])
    return str(correos[0]["email_address"])


def _nombre(data: dict) -> str:
    partes = [data.get("first_name"), data.get("last_name")]
    completo = " ".join(p for p in partes if p).strip()
    # El nombre es NOT NULL en la base y Clerk lo deja vacio cuando el usuario
    # entra por SSO sin perfil completo. El correo es mejor marcador de
    # posicion que una cadena vacia: identifica a la persona en pantalla.
    return completo or _email(data)


def _tenant_id(data: dict) -> UUID:
    metadata = data.get("public_metadata") or {}
    crudo = metadata.get("tenant_id")
    if not crudo:
        raise DatosDeClerkInvalidos(
            "falta tenant_id en publicMetadata: revisar el JWT Template y el "
            "flujo de alta de usuarios en el dashboard de Clerk"
        )
    try:
        return UUID(str(crudo))
    except ValueError as exc:
        raise DatosDeClerkInvalidos(f"tenant_id no es un UUID: {crudo!r}") from exc


def _user_type(data: dict) -> str:
    metadata = data.get("public_metadata") or {}
    rol = str(metadata.get("role") or "")
    if rol in TIPOS_VALIDOS:
        return rol
    if rol:
        logger.warning(
            "Rol '%s' desconocido en publicMetadata; se usa '%s'.",
            rol,
            TIPO_POR_DEFECTO,
        )
    return TIPO_POR_DEFECTO


def _buscar(db: Session, clerk_id: str, email: str) -> User | None:
    """Busca primero por clerk_id y despues por email.

    El segundo intento es lo que permite adoptar un usuario que ya existia en
    la base antes de que hubiera Clerk: cuando esa persona entra por primera
    vez, se le pega el `clerk_id` a su fila en vez de crear un duplicado con
    el mismo correo, que ademas violaria el UNIQUE de `email`.
    """
    por_clerk = db.scalar(select(User).where(User.clerk_id == clerk_id))
    if por_clerk is not None:
        return por_clerk
    return db.scalar(select(User).where(User.email == email))


def procesar_evento(db: Session, tipo: str, data: dict) -> str:
    """Aplica un evento de Clerk. Devuelve que se hizo, para el log y los tests.

    No hace commit: eso queda del lado del router, para que un fallo posterior
    en el mismo request no deje la fila a medias.
    """
    if tipo not in EVENTOS_SOPORTADOS:
        # 200 y no error: Clerk reintenta lo que no responde 2xx, y no tiene
        # sentido que reintente para siempre un evento que jamas vamos a usar.
        logger.info("Evento de Clerk ignorado: %s", tipo)
        return "ignorado"

    clerk_id = data.get("id")
    if not clerk_id:
        raise DatosDeClerkInvalidos("el evento no trae el id del usuario")
    clerk_id = str(clerk_id)

    if tipo == "user.deleted":
        usuario = db.scalar(select(User).where(User.clerk_id == clerk_id))
        if usuario is None:
            return "sin_efecto"
        # No se borra la fila: `audit_log` referencia `user_id`, y borrarla
        # dejaria huerfano el historial que RNF-08 exige conservar. Se le quita
        # el acceso, que es lo que "eliminar en Clerk" significa de verdad:
        # perdio su medio de autenticacion, no su rastro.
        usuario.status = "disabled"
        db.flush()
        return "deshabilitado"

    email = _email(data)
    usuario = _buscar(db, clerk_id, email)

    if usuario is None:
        usuario = User(
            clerk_id=clerk_id,
            email=email,
            full_name=_nombre(data),
            tenant_id=_tenant_id(data),
            user_type=_user_type(data),
            status="active",
        )
        db.add(usuario)
        db.flush()
        return "creado"

    # Solo se tocan los campos de los que Clerk es dueño. El tenant y el rol no
    # se pisan en cada actualizacion: si un admin los cambio en Ambienta, un
    # `user.updated` disparado porque la persona se cambio la foto no deberia
    # revertirlo.
    usuario.clerk_id = clerk_id
    usuario.email = email
    usuario.full_name = _nombre(data)
    if usuario.status == "invited":
        # Entro por primera vez: la invitacion se consumio.
        usuario.status = "active"
    db.flush()
    return "actualizado"
