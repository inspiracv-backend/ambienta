"""Clave local con RUT para quien entro por un proveedor externo (RF-06).

Alguien entra con Google, y despues quiere poder entrar con su RUT y una clave
—porque el correo corporativo cambia, porque el proveedor se cae, o
simplemente porque es como se identifica la gente en Chile—. Este modulo fija
esa credencial **sin quitarle el acceso que ya tenia**.

## La clave la guarda Clerk, no nosotros

`users.password_hash` existe en el esquema, asi que tecnicamente podriamos
autenticar por nuestra cuenta. Se descarto (decision D1): serian **dos
almacenes de contrasenas, dos politicas de robustez y dos lugares donde revocar
una sesion**, mas emitir tokens propios — justo lo que ADR-006 saco de la API.

El invitado si tiene credenciales propias, y la diferencia importa: las suyas no
abren ningun endpoint de negocio. Estas si.

## El RUT no se puede mandar tal cual

Clerk rechaza un `username` que sea **solo digitos**, y un RUT lo es salvo
cuando el verificador es K: funciona en 1 de cada 11 casos, que es la peor clase
de error —parece que anda—. Por eso el prefijo `rut` (D1).

La persona nunca lo escribe ni lo ve: lo antepone la pantalla al ingresar y lo
antepone este modulo al fijar. Que la transformacion viva en **una sola
funcion** es lo que impide que las dos puntas se desincronicen.

## Por que hay un User-Agent de navegador

Delante de la API de Clerk hay Cloudflare, y a un cliente que no se identifica
como navegador le responde **403 con `error code: 1010`**. Se lee como "la clave
secreta no sirve" y no tiene nada que ver. Es el mismo tropiezo que ya costo
tiempo con Ley Chile, ahi con un 401.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..rut import es_valido, normalizar

logger = logging.getLogger(__name__)

CLERK_API = "https://api.clerk.com/v1"

#: Cloudflare bloquea a quien no se identifica como navegador. Ver el docstring.
NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

#: Prefijo del `username` en Clerk (D1).
#:
#: **No es decoracion.** Garantiza el caracter no numerico en los 11 casos, y
#: evita que un RUT choque con cualquier otro esquema de username que se adopte
#: despues.
PREFIJO = "rut"

#: Largo minimo de la clave local.
#:
#: Es la clave de un usuario de negocio con acceso a los 109 endpoints, no la de
#: un invitado que solo ve sus tickets. Clerk aplica ademas su propia politica
#: —incluida la lista de contrasenas filtradas—, asi que esto es el piso, no el
#: techo: **Clerk puede rechazar una clave que aca pase**, y su mensaje se
#: devuelve tal cual porque explica mejor que uno nuestro.
LARGO_MINIMO_DE_CLAVE = 8


class ErrorDeClaveLocal(Exception):
    """Algo que la persona puede corregir. El mensaje se le muestra."""


class RutOcupado(ErrorDeClaveLocal):
    """El RUT ya lo tiene otra cuenta.

    **El mensaje no dice de quien.** Decirlo convertiria este formulario en una
    forma de averiguar si una persona concreta es usuaria del sistema, con solo
    escribir su RUT.
    """


class ClerkNoDisponible(Exception):
    """Falta la clave secreta o Clerk no responde. No es culpa de quien llama."""


def username_de(rut_normalizado: str) -> str:
    """`12345678-5` -> `rut12345678-5`. La unica traduccion, en un solo lugar."""
    return f"{PREFIJO}{rut_normalizado.lower()}"


def rut_de(username: str) -> str | None:
    """El camino inverso. `None` si ese username no es un RUT nuestro."""
    if not username or not username.startswith(PREFIJO):
        return None
    return normalizar(username[len(PREFIJO) :])


def _clerk(metodo: str, ruta: str, cuerpo: dict[str, Any] | None = None) -> Any:
    """Una llamada a la Backend API de Clerk.

    Lanza `ClerkNoDisponible` si no hay con que autenticarse o si la red falla,
    y `ErrorDeClaveLocal` si Clerk rechaza el dato **con un motivo que la
    persona puede corregir** — una clave debil, un username tomado.
    """
    clave = get_settings().clerk_secret_key
    if not clave:
        raise ClerkNoDisponible(
            "Falta CLERK_SECRET_KEY: la API no puede administrar cuentas."
        )

    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(
        f"{CLERK_API}{ruta}",
        data=datos,
        method=metodo,
        headers={
            "Authorization": f"Bearer {clave}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": NAVEGADOR,
        },
    )

    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            return json.loads(respuesta.read().decode() or "null")
    except urllib.error.HTTPError as exc:
        crudo = exc.read().decode(errors="replace")
        if exc.code in (400, 422):
            # Clerk explica por que en su propio idioma de errores, y su mensaje
            # suele ser mas util que uno nuestro ("esta contrasena aparece en
            # filtraciones conocidas" no lo sabemos nosotros).
            raise ErrorDeClaveLocal(_motivo(crudo)) from exc
        logger.error("Clerk respondio %s en %s %s: %s", exc.code, metodo, ruta, crudo[:300])
        raise ClerkNoDisponible(f"Clerk respondio {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.error("No se pudo contactar a Clerk: %s", exc)
        raise ClerkNoDisponible("No se pudo contactar al proveedor de identidad.") from exc


def _motivo(cuerpo_crudo: str) -> str:
    """El mensaje de Clerk, o uno generico si no se entiende su respuesta."""
    try:
        errores = json.loads(cuerpo_crudo).get("errors") or []
        mensajes = [e.get("long_message") or e.get("message") for e in errores]
        util = " ".join(m for m in mensajes if m)
        if util:
            return util
    except (ValueError, AttributeError):
        pass
    return "El proveedor de identidad rechazo el dato."


@dataclass
class ClaveLocalFijada:
    rut: str
    username: str


def _rut_de_otro(db: Session, rut: str, user_id: UUID) -> bool:
    """Si ese RUT ya es de **otra** fila de `users`.

    Se pregunta primero a nuestra base y no a Clerk porque aca la respuesta es
    exacta y barata. Clerk vuelve a comprobarlo igual —su `username` es unico
    globalmente— y esa es la comprobacion que manda: entre las dos hay una
    ventana de carrera, y la que gana es la del proveedor.

    Ojo: esta consulta corre bajo RLS, asi que **solo ve la empresa de la
    sesion**. Un RUT usado en otra empresa no aparece aca y lo detecta Clerk.
    Es correcto que sea asi: decir "ese RUT ya existe" mirando todas las
    empresas filtraria que esa persona es usuaria de otro cliente nuestro.
    """
    otro = db.execute(
        text(
            "SELECT 1 FROM users "
            "WHERE rut_tax_id = :r AND id <> :u AND deleted_at IS NULL"
        ),
        {"r": rut, "u": user_id},
    ).scalar()
    return bool(otro)


def fijar(
    db: Session, *, user_id: UUID, clerk_id: str, rut: str, clave: str
) -> ClaveLocalFijada:
    """Fija el RUT y la clave local. **No hace `commit`.**

    El orden importa: primero se valida todo lo barato, despues se escribe en
    Clerk, y **al final** en nuestra base. Si Clerk rechaza, no queda un
    `rut_tax_id` nuestro apuntando a una credencial que no existe.

    Lo que si puede quedar descuadrado es lo contrario: Clerk acepta y nuestra
    transaccion se cae despues. En ese caso la persona **ya puede entrar con su
    RUT** aunque nuestra fila no lo diga; volver a fijarlo lo arregla, porque
    poner el mismo username en la misma cuenta no es un error para Clerk.
    """
    normalizado = normalizar(rut)
    if normalizado is None or not es_valido(normalizado):
        raise ErrorDeClaveLocal(
            "El RUT no es valido: revisa el numero y el digito verificador."
        )

    if len(clave) < LARGO_MINIMO_DE_CLAVE:
        raise ErrorDeClaveLocal(
            f"La clave debe tener al menos {LARGO_MINIMO_DE_CLAVE} caracteres."
        )

    if not clerk_id:
        # Pasa en desarrollo sin Clerk, donde la sesion no identifica a nadie.
        # Fijar una clave para "el usuario actual" cuando no se sabe quien es no
        # tiene un resultado correcto posible.
        raise ClerkNoDisponible(
            "La sesion no identifica una cuenta del proveedor de identidad."
        )

    if _rut_de_otro(db, normalizado, user_id):
        raise RutOcupado("Ese RUT ya esta registrado.")

    usuario = username_de(normalizado)
    try:
        _clerk("PATCH", f"/users/{clerk_id}", {"username": usuario, "password": clave})
    except ErrorDeClaveLocal as exc:
        # Clerk tambien rechaza un username tomado, y ahi tampoco se dice de
        # quien es. Se traduce a nuestro error para que el router responda 409.
        if "username" in str(exc).lower() and (
            "taken" in str(exc).lower() or "use" in str(exc).lower()
        ):
            raise RutOcupado("Ese RUT ya esta registrado.") from exc
        raise

    # D5: el RUT tambien vive en `users`, duplicado a proposito. Es dato de
    # negocio —sale en informes y en el perfil— y no se puede depender de una
    # llamada a Clerk en cada pantalla que lo muestre.
    db.execute(
        text("UPDATE users SET rut_tax_id = :r WHERE id = :u"),
        {"r": normalizado, "u": user_id},
    )

    return ClaveLocalFijada(rut=normalizado, username=usuario)
