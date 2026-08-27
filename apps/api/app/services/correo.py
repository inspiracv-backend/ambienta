"""Envio de correo por Resend (#122).

`provider_message_id` de `notifications` ya decia, desde el esquema original,
"ID de Resend (decision cerrada #18 de la v1.7)". Esto la implementa.

## Lo que hace y lo que NO

**Envia.** La issue #122 dice ademas "recibir, leer y crear hilos", y eso es
otra cosa: recibir correo exige un dominio con MX apuntando al proveedor y un
endpoint publico que reciba sus webhooks, o sea infraestructura desplegada que
todavia no existe. Ademas se solapa con #72 (captura de correos entrantes hacia
el registro correspondiente). **No se implementa a medias**: un buzon de
entrada que a veces pierde correos es peor que no tenerlo, porque la gente
empieza a confiar en el.

## Sin llave no se inventa nada

Misma decision que el almacenamiento y que `TOKEN_INVITADO_SECRETO`: sin
`RESEND_API_KEY` no hay transporte, los correos esperan encolados **sin gastar
intentos** y las notificaciones in-app se entregan igual. Lo que no se hace es
escribir el correo a un archivo de log y dar el aviso por entregado, que es la
tentacion habitual y produce exactamente el peor resultado de este dominio: la
empresa cree que le avisaron.

## Los tres tipos de fallo, y por que se distinguen

| Que responde Resend | Como se trata | Por que |
|---|---|---|
| 401, 403 | **corta la corrida** | La llave no sirve. Va a fallar identico con el aviso siguiente: seguir gastaria los cinco intentos de la cola entera |
| 422, 400 | permanente | El correo esta mal formado o la direccion no existe. Reintentarlo no lo arregla y cada intento se paga |
| 429, 5xx, red | reintentable | Corte breve o limite de tasa. Es para lo que existe el retroceso |

La distincion no es cosmetica. Tratar 401 como permanente **mataria cada aviso
encolado en su primer intento**: se arregla la llave y todo lo pendiente ya
esta en `failed`.
"""
from __future__ import annotations

import logging

import httpx

from ..config import get_settings
from .despacho import ErrorDeConfiguracion, ErrorDeEnvio, ErrorPermanente

logger = logging.getLogger("ambienta.correo")

API = "https://api.resend.com/emails"

#: Resend contesta rapido o no contesta. Treinta segundos es holgado para su
#: percentil alto y evita que el despachador quede colgado con el candado
#: tomado: mientras espera, ese aviso no lo puede atender nadie mas.
TIEMPO_MAXIMO = 30.0

#: Cortan la corrida entera en vez de matar el aviso.
DE_CONFIGURACION = frozenset({401, 403})

#: No tiene arreglo reintentando.
PERMANENTES = frozenset({400, 404, 422})


def esta_configurado() -> bool:
    s = get_settings()
    return bool(s.resend_api_key and s.correo_remitente)


def _faltantes() -> list[str]:
    s = get_settings()
    faltan = []
    if not s.resend_api_key:
        faltan.append("RESEND_API_KEY")
    if not s.correo_remitente:
        faltan.append("CORREO_REMITENTE")
    return faltan


class TransporteResend:
    """Entrega por la API de Resend. Cumple el protocolo `despacho.Transporte`."""

    def __init__(self, *, api_key: str, remitente: str, responder_a: str | None = None):
        self._api_key = api_key
        self._remitente = remitente
        self._responder_a = responder_a

    def enviar(self, *, destino: str, asunto: str, cuerpo: str, contexto: dict) -> str:
        cuerpo_peticion: dict = {
            "from": self._remitente,
            "to": [destino],
            "subject": asunto or "(sin asunto)",
            "text": cuerpo,
        }
        if self._responder_a:
            cuerpo_peticion["reply_to"] = self._responder_a

        try:
            respuesta = httpx.post(
                API,
                json=cuerpo_peticion,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=TIEMPO_MAXIMO,
            )
        except httpx.HTTPError as exc:
            # Red caida, DNS, timeout. Reintentable por definicion.
            raise ErrorDeEnvio(f"no se pudo hablar con Resend: {exc}") from exc

        if respuesta.status_code in DE_CONFIGURACION:
            raise ErrorDeConfiguracion(
                f"Resend rechazo la llave (HTTP {respuesta.status_code}). "
                "Revisar RESEND_API_KEY y que el dominio de CORREO_REMITENTE "
                "este verificado."
            )

        if respuesta.status_code in PERMANENTES:
            raise ErrorPermanente(
                f"Resend rechazo el mensaje (HTTP {respuesta.status_code}): "
                f"{_detalle(respuesta)}"
            )

        if respuesta.status_code >= 400:
            raise ErrorDeEnvio(
                f"Resend respondio {respuesta.status_code}: {_detalle(respuesta)}"
            )

        identificador = _identificador(respuesta)
        if not identificador:
            # Respondio bien pero sin id. Se trata como reintentable: sin el
            # identificador no se puede rastrear despues un correo que el
            # cliente dice no haber recibido, y darlo por entregado seria
            # perder esa trazabilidad en silencio.
            raise ErrorDeEnvio(
                f"Resend respondio {respuesta.status_code} sin identificador de mensaje"
            )
        return identificador


def _detalle(respuesta: httpx.Response) -> str:
    """El mensaje de Resend, que dice mucho mas que el codigo suelto."""
    try:
        datos = respuesta.json()
    except ValueError:
        return respuesta.text[:200]
    if isinstance(datos, dict):
        return str(datos.get("message") or datos.get("error") or datos)[:200]
    return str(datos)[:200]


def _identificador(respuesta: httpx.Response) -> str | None:
    try:
        datos = respuesta.json()
    except ValueError:
        return None
    return datos.get("id") if isinstance(datos, dict) else None


def transporte_configurado() -> TransporteResend | None:
    """El transporte, o None si falta configuracion.

    Devuelve None en vez de levantar porque quien lo llama es el cron, y sin
    correo configurado el cron **tiene que seguir**: las notificaciones in-app
    se entregan igual y los correos esperan sin gastar intentos.
    """
    if not esta_configurado():
        logger.info(
            "Sin proveedor de correo (faltan %s). Los correos quedan encolados.",
            ", ".join(_faltantes()),
        )
        return None
    s = get_settings()
    return TransporteResend(
        api_key=s.resend_api_key,
        remitente=s.correo_remitente,
        responder_a=s.correo_responder_a or None,
    )
