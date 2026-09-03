"""Cabeceras de seguridad en las respuestas de la API.

Medido el 1-sep-2026: la API **no devolvia ninguna** —sin HSTS, sin
`X-Content-Type-Options`, sin `X-Frame-Options`, sin politica de referente— y
ademas anunciaba el servidor en la cabecera `server`.

Ninguna de esas ausencias es un agujero por si sola. Lo que hacen es dejarle al
navegador decisiones que puede tomar mal, y al atacante informacion que no
tiene por que tener. Es endurecimiento, y por eso el modulo entero se explica
cabecera por cabecera: la que no se entiende, tarde o temprano alguien la
borra.

## Por que middleware y no cabeceras por endpoint

Son casi 300 operaciones. Ponerlas una por una es una decision que se puede
olvidar, y olvidarla **no falla**: la respuesta sale igual, solo que sin
proteger. Es el mismo criterio que la guarda de permisos derivada de la ruta.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import get_settings

#: Cuanto dura la instruccion de "hablame solo por HTTPS".
#:
#: Un ano. Menos no sirve de mucho —la ventana de un ataque de degradacion es
#: justo la primera visita— y mas no aporta: el navegador renueva el plazo en
#: cada respuesta.
HSTS_SEGUNDOS = 31536000

#: Las que se mandan siempre, en cualquier entorno.
SIEMPRE = {
    # El navegador respeta el `Content-Type` declarado en vez de adivinarlo.
    # Sin esto, un archivo subido por un usuario y servido como texto plano
    # puede terminar interpretado como HTML, y con el HTML viene el script.
    "X-Content-Type-Options": "nosniff",
    # Nadie puede meter estas respuestas en un marco. Es una API que devuelve
    # JSON y una pagina de documentacion: ninguna necesita ser embebida, y
    # permitirlo habilita el secuestro de clics sobre `/docs`.
    "X-Frame-Options": "DENY",
    # Lo mismo que la anterior pero en el estandar que la reemplaza. Van las
    # dos porque no todos los navegadores en uso soportan `frame-ancestors`.
    "Content-Security-Policy": "frame-ancestors 'none'",
    # La URL de la API no viaja al sitio de destino cuando alguien sigue un
    # enlace desde una respuesta. Importa porque nuestras rutas llevan
    # identificadores de empresa y de documento.
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # El navegador no le concede camara, microfono ni ubicacion a esta pagina.
    # No los pide; declararlo evita que un `iframe` heredado los pida por ella.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

#: Se reemplaza en vez de borrarse: quitarla del todo es tambien una senal.
SERVIDOR = "ambienta"


class CabecerasDeSeguridad(BaseHTTPMiddleware):
    """Agrega las cabeceras a toda respuesta, incluidas las de error.

    ## Lo que NO hace, y por que

    **No pone una `Content-Security-Policy` completa.** La pagina `/docs` es
    Swagger UI y carga su hoja de estilos y su script desde un CDN; una
    politica estricta la dejaria en blanco, y una pagina de documentacion rota
    se lee como una API rota. Lo que si se aplica es `frame-ancestors`, que
    protege contra el secuestro de clics sin tocar de donde se cargan los
    recursos.

    **No manda `X-XSS-Protection`.** Esta obsoleta: los navegadores actuales la
    ignoran, y en los que la respetaban su filtro introdujo vulnerabilidades
    propias. Mandarla seria ruido que aparenta proteccion.

    **HSTS solo en produccion.** Es una instruccion que el navegador
    **recuerda**: si se emitiera en desarrollo, quien abra `localhost` por HTTP
    despues de haber entrado por HTTPS a otro proyecto en el mismo puerto se
    queda sin poder acceder, y el error no se parece en nada a la causa.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        respuesta = await call_next(request)

        for cabecera, valor in SIEMPRE.items():
            # `setdefault`: si un endpoint declaro la suya a proposito —una
            # descarga con su propia politica— no se le pisa.
            respuesta.headers.setdefault(cabecera, valor)

        respuesta.headers["server"] = SERVIDOR

        if get_settings().environment == "production":
            respuesta.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={HSTS_SEGUNDOS}; includeSubDomains",
            )

        return respuesta
