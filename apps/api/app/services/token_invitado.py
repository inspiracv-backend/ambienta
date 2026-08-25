"""La sesion del Cliente Invitado: token propio, 30 dias (RF-01, RF-02, RF-07).

## Por que un token propio y no uno de Clerk

El invitado **no es cuenta de Clerk** (decision D2), asi que Clerk no tiene a
quien firmarle nada. Y no se le puede dar un token de los otros: los dos
emisores tienen que seguir separados, porque es lo unico que impide que un
endpoint de negocio acepte a un invitado por descuido.

Decision del equipo el 22-ago-2026: **token propio, 30 dias**, la misma vigencia
que la credencial.

## HS256 y no RS256

El mismo servicio firma y verifica. Un par de llaves sirve cuando alguien tiene
que validar sin poder emitir —el caso de Clerk, que firma para muchas apps— y
aca no hay tal tercero. Simetrico es menos piezas que mantener.

## El token no es la autorizacion, es solo la identidad

Dice de que empresa es el invitado y con que credencial entro. **No dice que
puede hacer**, y eso es a proposito: lo que puede hacer lo decide el endpoint,
y hoy son dos. Meter permisos adentro convertiria un token de 30 dias en una
autorizacion que no se puede revocar sin esperar a que caduque.

Por eso `verificar()` devuelve la credencial y **quien llama tiene que ir a la
base** a comprobar que siga viva. Un token valido sobre una credencial revocada
no sirve: si no, revocar no revocaria nada durante un mes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from ..config import get_settings

logger = logging.getLogger(__name__)

ALGORITMO = "HS256"

#: Quien emite estos tokens. Se valida al verificar para que un JWT de otra
#: procedencia —incluido uno de Clerk— no pueda hacerse pasar por uno de estos
#: aunque alguien llegara a compartir el secreto.
EMISOR = "ambienta/acceso-invitado"

#: Marca el proposito del token dentro del propio payload.
#:
#: No sobra: sin ella, cualquier otro token que esta API firmara en el futuro
#: con el mismo secreto valdria como sesion de invitado. Es barato ahora y caro
#: de agregar despues.
TIPO = "invitado"


class SecretoSinConfigurar(RuntimeError):
    """No hay con que firmar. **Se falla, no se improvisa una llave.**

    Firmar con un valor por defecto haria que cualquiera que lea el repositorio
    pueda emitirse una sesion de invitado de la empresa que quiera. Preferible
    un 503 explicito que un acceso que parece protegido y no lo esta.
    """


def emitir(
    *, tenant_id: UUID, credencial_id: UUID, rut: str, dias: int
) -> tuple[str, datetime]:
    """Firma la sesion. Devuelve `(token, cuando expira)`.

    `dias` lo pasa quien llama y no lo decide este modulo: la vigencia del token
    tiene que ser **la de la credencial**, no una constante paralela que pueda
    quedar mas larga. Un token que sobrevive a su credencial es un acceso que no
    se puede cortar.
    """
    secreto = get_settings().token_invitado_secreto
    if not secreto:
        raise SecretoSinConfigurar(
            "Falta AMBIENTA_TOKEN_INVITADO_SECRETO. Sin esa variable no se "
            "pueden emitir sesiones de invitado."
        )

    expira = datetime.now(timezone.utc) + timedelta(days=dias)
    payload = {
        "iss": EMISOR,
        "tipo": TIPO,
        # `sub` es la credencial, no la persona: de un invitado no sabemos quien
        # es, y decir lo contrario en un token seria afirmar algo que no se
        # verifico.
        "sub": str(credencial_id),
        "tenant_id": str(tenant_id),
        "rut": rut,
        "exp": expira,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secreto, algorithm=ALGORITMO), expira


class SesionDeInvitado:
    """Lo que dice un token valido. **No es un `CurrentUser` y no debe serlo.**

    Es la misma decision que en `services/invitado.py`, sostenida aca: si los
    dos caminos desembocaran en el mismo tipo, cada endpoint de negocio tendria
    que acordarse de preguntar si quien llama es un invitado.
    """

    __slots__ = ("credencial_id", "tenant_id", "rut")

    def __init__(self, credencial_id: UUID, tenant_id: UUID, rut: str) -> None:
        self.credencial_id = credencial_id
        self.tenant_id = tenant_id
        self.rut = rut

    def __repr__(self) -> str:  # pragma: no cover - ayuda al depurar
        return f"SesionDeInvitado(rut={self.rut!r}, tenant_id={self.tenant_id!r})"


def verificar(token: str) -> SesionDeInvitado | None:
    """Valida la firma y devuelve la sesion. `None` si el token no sirve.

    Devuelve `None` y no lanza para todos los modos de fallo —firma invalida,
    vencido, emisor ajeno, tipo equivocado, payload deforme— porque quien llama
    responde lo mismo en todos los casos: 401. Distinguirlos hacia afuera solo
    le diria a quien prueba en que se equivoco.

    **Que el token sea valido no basta.** Dice que lo firmamos nosotros y que no
    caduco; no dice que la credencial siga viva. Quien llama tiene que
    comprobarla contra la base, o revocar no serviria de nada durante 30 dias.
    """
    secreto = get_settings().token_invitado_secreto
    if not secreto or not token:
        return None

    try:
        payload = jwt.decode(
            token,
            secreto,
            algorithms=[ALGORITMO],
            issuer=EMISOR,
            # `exp` lo valida la libreria; se deja explicito para que se vea que
            # no esta apagado.
            options={"verify_exp": True, "verify_iss": True},
        )
    except JWTError as exc:
        logger.info("Sesion de invitado rechazada: %s", exc)
        return None

    if payload.get("tipo") != TIPO:
        # Un token nuestro, firmado con el mismo secreto, pero emitido para otra
        # cosa. No es una sesion de invitado.
        logger.info("Token con tipo %r, no es una sesion de invitado", payload.get("tipo"))
        return None

    try:
        return SesionDeInvitado(
            credencial_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            rut=payload["rut"],
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.info("Sesion de invitado con payload deforme: %s", exc)
        return None
