"""Acceso temporal del Cliente Invitado (RF-01, RF-02, RF-07).

Una persona sin cuenta abre una solicitud y necesita poder volver a verla. El
analisis pide RUT y clave dinamica, **sin registro previo**.

## No es un usuario, y esa es toda la decision

Decision D2 del cambio, confirmada por el equipo: el invitado no es cuenta de
Clerk ni fila en `users`. RF-02 dice literalmente que no necesita cuenta; y
meterlos en `users` mezclaria a los empleados con terceros ocasionales, cuyo
volumen es por diseno el mas alto y el menos valioso de mantener.

## Lo que se pierde, y como se acota

Quedan **dos emisores de credenciales**, que es justo lo que ADR-006 quiso
evitar. Se acota con D3: el acceso del invitado **no abre ningun endpoint de
negocio**. La superficie donde importa que la identidad sea fuerte sigue
teniendo un solo emisor.

Por eso la validacion de aca **no pasa por `get_current_user`**. Si los dos
caminos desembocaran en el mismo `CurrentUser`, cada uno de los 109 endpoints
tendria que preguntarse si quien llama es un invitado — y basta olvidarlo en uno
para filtrar datos de la empresa a un tercero. Con dependencias separadas el
error por omision es negar: un endpoint de negocio no acepta credencial de
invitado porque ni siquiera sabe leerla.

## La vigencia no es un detalle

Son credenciales que se entregan **sin verificar quien las recibe**. Una
credencial sin caducidad emitida a un desconocido no se puede retirar. El equipo
fijo 30 dias.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..rut import digito_verificador, normalizar
from .auditoria import registrar

logger = logging.getLogger(__name__)

#: Cuanto vale el acceso de un invitado. Decidido por el equipo el 22-ago-2026.
#:
#: Renovable generando uno nuevo con el mismo link. No se extiende sola al
#: usarla: una credencial que se renueva con el uso nunca caduca, y entonces la
#: vigencia no significa nada.
DIAS_DE_VIGENCIA = 30

#: Alfabeto de la clave dinamica. **Sin `O`, `0`, `I` ni `1`.**
#:
#: Se dicta por telefono y se copia a mano: confundirlos produce intentos
#: fallidos que la persona lee como "me dieron mal la clave", y vuelve a pedir
#: acceso. Es la misma decision que ya tomo el generador del navegador.
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_LARGO_CLAVE = 6

#: Rango del cuerpo del RUT generado.
#:
#: Arranca en 90.000.000 —por encima de los RUT de personas reales, que hoy no
#: llegan ahi— para que un RUT emitido por nosotros **no colisione con el RUT
#: verdadero de nadie**. Si colisionara, dos personas distintas competirian por
#: la misma credencial dentro de la empresa.
_RUT_DESDE = 90_000_000
_RUT_HASTA = 99_999_999


@dataclass
class CredencialEmitida:
    """Lo que se le muestra a la persona **una sola vez**.

    La clave en claro vive solo en esta respuesta: en la base queda su hash. Si
    se pierde, se genera un acceso nuevo — no hay forma de recuperarla, y eso es
    la propiedad, no una limitacion.
    """

    rut: str
    clave: str
    valido_hasta: datetime


def _hash(clave: str, rut: str) -> str:
    """Hash de la clave, ligado al RUT.

    El RUT entra como sal: sin el, dos invitados con la misma clave de seis
    caracteres tendrian el mismo hash, y el alfabeto es chico.

    **No es `bcrypt`, y la diferencia importa.** Esta credencial es de un solo
    uso practico, vive 30 dias y no abre nada de negocio; el costo de un hash
    lento aca no compra mucho. Cuando exista clave de usuario real (RF-06) esa
    **si** necesita un algoritmo con costo configurable.
    """
    return hashlib.sha256(f"{rut}:{clave}".encode()).hexdigest()


def _rut_disponible(db: Session, tenant_id: UUID) -> str:
    """Un RUT valido que nadie tenga todavia en esta empresa.

    Reintenta porque el espacio es finito y la colision, aunque rara, existe.
    **No se reintenta para siempre**: si el rango se lleno, es un problema real
    que hay que ver, no algo que se resuelva insistiendo.
    """
    for _ in range(20):
        cuerpo = secrets.randbelow(_RUT_HASTA - _RUT_DESDE) + _RUT_DESDE
        candidato = f"{cuerpo}-{digito_verificador(cuerpo)}"
        ocupado = db.execute(
            text(
                "SELECT 1 FROM guest_credentials "
                "WHERE tenant_id = :t AND rut = :r"
            ),
            {"t": tenant_id, "r": candidato},
        ).scalar()
        if not ocupado:
            return candidato

    raise RuntimeError(
        "No se pudo generar un RUT de invitado libre despues de 20 intentos. "
        "El rango reservado esta agotado y hay que ampliarlo."
    )


def emitir(db: Session, tenant_id: UUID) -> CredencialEmitida:
    """Genera un acceso de invitado para esta empresa.

    **No hace `commit`.** Quien llama decide, para que la credencial y lo que se
    haga con ella entren o no entren juntos.

    La clave se devuelve en claro **una sola vez**: en la base va su hash.
    """
    rut = _rut_disponible(db, tenant_id)
    clave = "".join(secrets.choice(_ALFABETO) for _ in range(_LARGO_CLAVE))
    hasta = datetime.now(timezone.utc) + timedelta(days=DIAS_DE_VIGENCIA)

    db.execute(
        text(
            "INSERT INTO guest_credentials "
            "(tenant_id, rut, password_hash, valid_until) "
            "VALUES (:t, :r, :h, :v)"
        ),
        {"t": tenant_id, "r": rut, "h": _hash(clave, rut), "v": hasta},
    )

    return CredencialEmitida(rut=rut, clave=clave, valido_hasta=hasta)


@dataclass
class InvitadoAutenticado:
    """Quien es el invitado que llama. **Deliberadamente no es un `CurrentUser`.**

    Tipo distinto para que ningun endpoint de negocio lo acepte por accidente:
    la incompatibilidad la comprueba el verificador de tipos, no la memoria de
    quien escribe el endpoint.
    """

    credencial_id: UUID
    tenant_id: UUID
    rut: str


def autenticar(
    db: Session, tenant_id: UUID, rut: str, clave: str
) -> InvitadoAutenticado | None:
    """Valida un RUT y una clave contra las credenciales de **esa** empresa.

    Devuelve `None` si no sirven, sin distinguir por que: **RUT inexistente,
    clave incorrecta, credencial vencida y credencial de otra empresa dan lo
    mismo hacia afuera**. Decir cual fallo le confirmaria a quien prueba al azar
    que un RUT existe en esa empresa.

    El motivo si queda en el registro del servidor, que es donde sirve para
    diagnosticar sin filtrar nada.
    """
    normalizado = normalizar(rut)
    if normalizado is None or not clave:
        return None

    fila = db.execute(
        text(
            "SELECT id, password_hash, valid_until, revoked_at "
            "FROM guest_credentials WHERE tenant_id = :t AND rut = :r"
        ),
        {"t": tenant_id, "r": normalizado},
    ).first()

    if fila is None:
        logger.info("Invitado: RUT %s no existe en la empresa %s", normalizado, tenant_id)
        return None

    cred_id, hash_guardado, valido_hasta, revocada = fila

    # `compare_digest` y no `==`: comparar hashes con el operador normal filtra
    # por tiempo cuantos caracteres coincidieron. Sobre un hash el ataque es
    # poco practico, pero la version segura cuesta lo mismo de escribir.
    if not hmac.compare_digest(hash_guardado, _hash(clave, normalizado)):
        logger.info("Invitado: clave incorrecta para %s", normalizado)
        return None

    if revocada is not None:
        logger.info("Invitado: credencial revocada %s", cred_id)
        return None

    if valido_hasta <= datetime.now(timezone.utc):
        logger.info("Invitado: credencial vencida %s (vencio %s)", cred_id, valido_hasta)
        return None

    # Se registra el uso, no se extiende la vigencia. Una credencial que se
    # renueva sola al usarla nunca caduca.
    db.execute(
        text("UPDATE guest_credentials SET last_used_at = now() WHERE id = :i"),
        {"i": cred_id},
    )

    # Y se anota la entrada en el registro de actividades, **a mano**.
    #
    # El observador automatico mira lo que pasa por la ORM, y esta tabla se
    # escribe con SQL crudo: sin esta llamada, el unico acceso del sistema que
    # no requiere cuenta seria tambien el unico que no deja rastro. `login` es
    # una de las siete acciones que acepta la base.
    #
    # Sin actor: un invitado no es un usuario, y `actor_user_id` apunta a
    # `users`. Quien entro queda en el `metadata`, que es donde puede estar.
    registrar(
        db,
        tenant_id=tenant_id,
        action="login",
        entity_type="guest_credentials",
        entity_id=cred_id,
        metadata={"rut": normalizado, "via": "credencial_de_invitado"},
    )

    return InvitadoAutenticado(
        credencial_id=cred_id, tenant_id=tenant_id, rut=normalizado
    )
