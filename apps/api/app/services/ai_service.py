"""El puente hacia el AI Service (RF-59 a RF-63).

**La API es la fachada: el navegador nunca habla con el AI Service.** Eso no es
una preferencia de arquitectura, es lo que sostiene dos cosas:

1. **El AI Service no se publica a internet.** Vive en la red interna del
   compose (`http://ai-service:8100`) y sólo esta API lo alcanza. Un puerto
   abierto de un servicio que consulta la base con el token de quien pregunta
   es una puerta que nadie vigila.
2. **La empresa sale del token verificado y de ningún otro lado.** El cuerpo, la
   query y las cabeceras del cliente no deciden a qué empresa se consulta. Esta
   capa es la que lo garantiza.

## Lo que este módulo NO hace, a propósito

**No guarda nada.** La conversación la persiste el AI Service llamando a
`/support/chatbot` con el mismo token. Si la fachada guardara también la
pregunta o la respuesta, cada turno quedaría escrito dos veces — y el duplicado
no se ve como un error: se ve como un historial raro que alguien revisa tres
semanas después.

**No reinterpreta el streaming.** Los eventos `herramienta`, `texto`, `final` y
`error` pasan tal cual. El `texto` es la generación en curso, no la respuesta
final: tratarlo como respuesta dejaría guardado un fragmento a medias.

## El token viaja sin transformarse

Se reenvía el `Authorization: Bearer <JWT>` original. **No hay un secreto
compartido entre los dos servicios**, y es deliberado: con uno, el AI Service
podría consultar cualquier empresa y la única barrera sería que el código no se
equivoque. Con el token de quien pregunta, RLS sigue siendo la barrera y el
alcance es el de esa persona.

En modo desarrollo —sin `CLERK_JWKS_URL`— no hay token, así que se reenvía
`X-Tenant-Id` con la empresa que la sesión ya declaró. **Derivada acá, no
copiada del cliente**: es la diferencia entre una cabecera de desarrollo y un
parámetro con el que cualquiera elige empresa.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from ..config import get_settings

logger = logging.getLogger(__name__)

#: Conectar tiene que ser rápido —es la red interna del compose— pero **leer no
#: puede serlo**: del otro lado hay un modelo generando. Un timeout de lectura
#: corto no "protege": corta respuestas a medio escribir y deja al AI Service
#: terminando un trabajo que nadie va a recibir.
#:
#: Acotado igual, porque sin tope una generación colgada retiene un worker de
#: uvicorn para siempre.
TIEMPO = httpx.Timeout(connect=5.0, read=180.0, write=10.0, pool=5.0)

#: El tipo que pide el streaming. Se compara contra el `Accept` del cliente.
SSE = "text/event-stream"

#: Códigos que el AI Service usa con un significado que el cliente entiende, y
#: que por eso se dejan pasar con su propio mensaje. Cualquier otro se traduce a
#: 503: un 500 del servicio de IA no es un error del cliente.
CODIGOS_PROPIOS = frozenset({
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_ENTITY,
    status.HTTP_503_SERVICE_UNAVAILABLE,
})

CODIGO_SIN_CONFIGURAR = "ai_service_sin_configurar"
CODIGO_NO_RESPONDE = "ai_service_no_responde"


def esta_configurado() -> bool:
    """Si hay a dónde consultar. La pantalla lo usa para no ofrecer el chat en vano."""
    return bool(get_settings().ai_service_url)


def _url() -> str:
    """La base del AI Service, o 503 con un mensaje que dice qué falta.

    **Sin la variable responde 503 y no un 500.** Es el mismo criterio que el
    almacenamiento y el correo: una capacidad sin configurar se declara, no se
    cae. Lo que no se hace es caer a un valor por defecto —`localhost:8100`—
    porque en producción eso es una conexión a nada que tarda en fallar.
    """
    base = get_settings().ai_service_url
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "codigo": CODIGO_SIN_CONFIGURAR,
                "mensaje": (
                    "El servicio de IA no esta configurado en este entorno. "
                    "Falta AI_SERVICE_URL."
                ),
            },
        )
    return base.rstrip("/")


def cabeceras(
    *,
    token: str | None,
    tenant_id: UUID,
    acepta: str,
    request_id: str | None = None,
) -> dict[str, str]:
    """Lo que viaja al AI Service, y nada más.

    `token` es el JWT original de quien pregunta, tal como llegó. Si no hay
    —modo desarrollo—, va `X-Tenant-Id` con la empresa **que esta API ya
    resolvió**, no con la que el cliente haya pedido.
    """
    h = {"Accept": acepta, "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    else:
        h["X-Tenant-Id"] = str(tenant_id)
    # Para poder cruzar una consulta lenta entre los logs de los dos servicios.
    if request_id:
        h["X-Request-Id"] = request_id
    return h


def cuerpo(*, pregunta: str, conversation_id: UUID | None, fecha: str | None) -> dict:
    """El cuerpo del contrato, **sin los opcionales vacíos**.

    El contrato los declara nulables, pero mandar `conversation_id: null`
    explícito y no mandarlo son lo mismo para el AI Service y distinto para
    quien lee un log. Se omiten.
    """
    datos: dict[str, Any] = {"pregunta": pregunta}
    if conversation_id is not None:
        datos["conversation_id"] = str(conversation_id)
    if fecha:
        datos["fecha"] = fecha
    return datos


def _traducir(respuesta: httpx.Response) -> HTTPException:
    """El error del AI Service, convertido en uno público.

    **Nunca se devuelve el cuerpo crudo de otro servicio.** Puede traer la
    traza, el nombre de un host interno o el detalle de una consulta; y un
    cliente no tiene por qué distinguir "el modelo se cayó" de "la base de
    conocimiento no respondió".
    """
    try:
        detalle = respuesta.json()
    except ValueError:
        detalle = None

    if respuesta.status_code in CODIGOS_PROPIOS:
        mensaje = None
        if isinstance(detalle, dict):
            # El contrato del AI Service usa `detail` (FastAPI) o `mensaje`.
            crudo = detalle.get("mensaje") or detalle.get("detail")
            if isinstance(crudo, str):
                mensaje = crudo
            elif isinstance(crudo, dict):
                mensaje = crudo.get("mensaje")
        return HTTPException(
            status_code=respuesta.status_code,
            detail=mensaje or "El servicio de IA rechazo la consulta.",
        )

    logger.error(
        "El AI Service respondio %s a una consulta: %s",
        respuesta.status_code,
        respuesta.text[:300],
    )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "codigo": CODIGO_NO_RESPONDE,
            "mensaje": "El servicio de IA no pudo responder. Intentar de nuevo.",
        },
    )


def _sin_red(exc: httpx.HTTPError) -> HTTPException:
    logger.error("No se pudo alcanzar el AI Service: %s: %s", type(exc).__name__, exc)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "codigo": CODIGO_NO_RESPONDE,
            "mensaje": "El servicio de IA no responde. Intentar de nuevo en un momento.",
        },
    )


def consultar(*, datos: dict, encabezados: dict[str, str]) -> dict:
    """Una consulta completa: se espera la respuesta y se devuelve su JSON."""
    try:
        respuesta = httpx.post(
            f"{_url()}/consulta", json=datos, headers=encabezados, timeout=TIEMPO
        )
    except httpx.HTTPError as exc:
        raise _sin_red(exc) from exc

    if respuesta.status_code != status.HTTP_200_OK:
        raise _traducir(respuesta)

    try:
        return respuesta.json()
    except ValueError as exc:  # pragma: no cover - el contrato dice JSON
        logger.error("El AI Service respondio 200 con un cuerpo que no es JSON.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "codigo": CODIGO_NO_RESPONDE,
                "mensaje": "El servicio de IA devolvio una respuesta ilegible.",
            },
        ) from exc


def consultar_en_streaming(*, datos: dict, encabezados: dict[str, str]) -> Iterator[bytes]:
    """Los eventos del AI Service, retransmitidos tal cual y en orden.

    **Se reenvían los bytes, no una reconstrucción.** Rearmar los eventos a
    partir de lo parseado invita a perder uno —`herramienta`, por ejemplo, que
    el frontend usa para mostrar "estoy buscando en la normativa"— y a cambiar
    el orden, que es justo lo que un stream promete conservar.

    Si el AI Service falla **antes** de empezar a emitir, se levanta el error
    traducido como en una consulta normal. Si falla **a mitad del stream**, ya
    no hay forma de cambiar el código HTTP: se emite un evento `error` propio,
    que es lo que el contrato declara y lo que el frontend sabe mostrar.
    """
    try:
        with httpx.stream(
            "POST", f"{_url()}/consulta", json=datos, headers=encabezados, timeout=TIEMPO
        ) as respuesta:
            if respuesta.status_code != status.HTTP_200_OK:
                # Hay que leer el cuerpo antes de tocarlo: en `stream` no viene.
                respuesta.read()
                raise _traducir(respuesta)
            try:
                for trozo in respuesta.iter_raw():
                    if trozo:
                        yield trozo
            except httpx.HTTPError as exc:
                logger.error("El stream del AI Service se corto: %s", exc)
                yield _evento_de_error(
                    "La generacion se interrumpio. La respuesta puede estar incompleta."
                )
    except httpx.HTTPError as exc:
        raise _sin_red(exc) from exc


def _evento_de_error(mensaje: str) -> bytes:
    cuerpo_json = json.dumps({"codigo": CODIGO_NO_RESPONDE, "mensaje": mensaje})
    return f"event: error\ndata: {cuerpo_json}\n\n".encode()
