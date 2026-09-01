"""Registrar de forma permanente a un Cliente Invitado (#142, RF-03).

## Por que esto no era un `PATCH` de rol

El diseno de RBAC lo describia como
`POST /admin/invitados/:userId/registrar-permanente`, o sea cambiarle el rol a
un usuario que ya existe. **En el modelo implementado no existe ese usuario.**

Un invitado vive en `guest_credentials`: RUT, clave y vigencia. No es una fila de
`users` — medido: cero usuarios con `user_type = 'guest'`. Es el segundo emisor
de identidad del sistema, con su propio tipo de token, a proposito.

Asi que registrar no es promover a alguien: es **crear a la persona** y llevarse
consigo lo que ya hizo.

## De donde salen el nombre y el correo

La credencial **no los tiene**, y `users` exige los dos. Salen de los tickets que
el invitado abrio: `support_tickets.guest_name` y `guest_email`. Es lo que
anticipaba `seccion-n-usuarios-roles-perfil.md` — "requeriria seleccionar un
contacto de `SupportTicket` y convertirlo en `User`".

Si el invitado nunca abrio un ticket, no hay de donde sacarlos y **se dice**, en
vez de inventar un nombre o dejar el correo vacio.

## Las tres cosas que pasan, y por que las tres

1. **Se crea el usuario**, con el RUT de la credencial.
2. **Sus tickets pasan a ser suyos** (`created_by_user_id`). Sin esto, la persona
   entra como usuaria y **no ve lo que ella misma abrio**: su historial quedaria
   colgando de una credencial que ya no puede usar.
3. **La credencial se revoca.** El sentido de "registro permanente" es dejar de
   ser invitado; conservarla dejaria dos caminos de entrada para la misma
   persona, uno de ellos con un token que ningun endpoint de negocio sabe leer.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from ..models.organization import User
from ..models.support import SupportTicket


class ErrorDeRegistro(Exception):
    """El invitado no se puede registrar con lo que hay."""


class InvitadoDesconocido(ErrorDeRegistro):
    """La credencial no corresponde a esta empresa, o no existe."""


class CredencialYaRevocada(ErrorDeRegistro):
    """Ya se registro, o alguien le quito el acceso."""


class SinNombreNiCorreo(ErrorDeRegistro):
    """No hay de donde sacar los datos que `users` exige."""


class CorreoYaRegistrado(ErrorDeRegistro):
    """Ese correo ya identifica a otra persona."""


def credencial(db: Session, tenant_id: UUID, credencial_id: UUID):
    """La credencial, leida con la sesion del tenant.

    Se consulta con SQL porque `guest_credentials` no tiene modelo ORM — el
    resto del modulo de invitados tambien la trata asi. Lo que importa es que
    la lectura pasa por RLS: si esta empresa no la ve, para ella no existe.
    """
    return db.execute(
        text(
            "SELECT id, rut, revoked_at FROM guest_credentials "
            "WHERE id = :c AND tenant_id = :t"
        ),
        {"c": str(credencial_id), "t": str(tenant_id)},
    ).first()


def datos_desde_sus_tickets(
    db: Session, tenant_id: UUID, credencial_id: UUID
) -> tuple[str | None, str | None]:
    """Nombre y correo del ticket **mas reciente** que dejo los dos.

    El mas reciente y no el primero: si la persona corrigio su correo en una
    solicitud posterior, el dato bueno es el ultimo que dio.

    Se exige que la fila tenga los dos y no se mezclan de tickets distintos —
    un nombre de uno con el correo de otro puede ser de dos personas que usaron
    la misma credencial, y eso crearia un usuario que no es ninguna de las dos.
    """
    fila = db.execute(
        select(SupportTicket.guest_name, SupportTicket.guest_email)
        .where(
            SupportTicket.tenant_id == tenant_id,
            SupportTicket.guest_credential_id == credencial_id,
            SupportTicket.guest_name.is_not(None),
            SupportTicket.guest_email.is_not(None),
            SupportTicket.deleted_at.is_(None),
        )
        .order_by(SupportTicket.created_at.desc())
        .limit(1)
    ).first()
    return (fila[0], fila[1]) if fila else (None, None)


def registrar_permanente(
    db: Session,
    tenant_id: UUID,
    credencial_id: UUID,
    department_id: UUID,
    *,
    full_name: str | None = None,
    email: str | None = None,
    user_type: str = "internal",
) -> tuple[User, list[str]]:
    """Convierte al invitado en usuario de la empresa, y dice que paso.

    `full_name` y `email` son opcionales: si no llegan, salen de sus tickets.
    Llegan cuando quien administra corrige el dato — la persona pudo escribir
    mal su correo al abrir la solicitud, y obligarla a arrastrar ese error seria
    absurdo.

    `department_id` **no** es opcional: `ck_users_interno_con_departamento`
    exige departamento a los tipos `internal` y `tenant_admin`, asi que sin el
    la fila la rechaza Postgres con un error que no se lee como lo que es.
    """
    cred = credencial(db, tenant_id, credencial_id)
    if cred is None:
        raise InvitadoDesconocido(
            "Esa credencial de invitado no corresponde a esta empresa."
        )
    if cred.revoked_at is not None:
        raise CredencialYaRevocada(
            "Esa credencial ya esta revocada. Si la persona ya se registro, "
            "busca su cuenta en Usuarios; si no, emitele una credencial nueva."
        )

    del_ticket = datos_desde_sus_tickets(db, tenant_id, credencial_id)
    nombre = (full_name or del_ticket[0] or "").strip()
    correo = (email or del_ticket[1] or "").strip()

    if not nombre or not correo:
        raise SinNombreNiCorreo(
            "No hay nombre ni correo para esta persona: la credencial solo "
            "guarda el RUT, y no abrio ninguna solicitud de donde tomarlos. "
            "Indicalos al registrarla."
        )

    # `users.email` es unico **en todo el sistema**, no por empresa. Se
    # comprueba antes para responder un 409 legible en vez de un error de
    # restriccion, que se lee como una falla del sistema.
    ya = db.scalars(
        select(User).where(func.lower(User.email) == correo.lower())
    ).first()
    if ya is not None:
        raise CorreoYaRegistrado(
            f"Ya hay una cuenta con el correo {correo}. Si es la misma persona, "
            "no hace falta registrarla otra vez."
        )

    efectos: list[str] = []

    usuario = User(
        tenant_id=tenant_id,
        department_id=department_id,
        rut_tax_id=cred.rut,
        email=correo,
        full_name=nombre,
        user_type=user_type,
        # `invited` y no `active`: la cuenta existe, pero la persona todavia no
        # entro por ella. Marcarla activa afirmaria un ingreso que no ocurrio, y
        # ese dato se usa despues para saber quien esta usando el sistema.
        status="invited",
    )
    db.add(usuario)
    db.flush()
    efectos.append(f"Se creo la cuenta de {nombre}")

    # Sus solicitudes pasan a ser suyas. `guest_credential_id` se conserva: es
    # el rastro de que entraron por el acceso de invitado, y borrarlo reescribiria
    # la historia.
    cuantos = db.execute(
        update(SupportTicket)
        .where(
            SupportTicket.tenant_id == tenant_id,
            SupportTicket.guest_credential_id == credencial_id,
            SupportTicket.created_by_user_id.is_(None),
        )
        .values(created_by_user_id=usuario.id)
    ).rowcount
    if cuantos:
        efectos.append(
            f"Sus {cuantos} solicitud(es) quedaron ligadas a la cuenta nueva"
        )

    db.execute(
        text(
            "UPDATE guest_credentials SET revoked_at = now() "
            "WHERE id = :c AND tenant_id = :t AND revoked_at IS NULL"
        ),
        {"c": str(credencial_id), "t": str(tenant_id)},
    )
    efectos.append("Se revoco su acceso de invitado: ahora entra con su cuenta")

    db.flush()
    return usuario, efectos
