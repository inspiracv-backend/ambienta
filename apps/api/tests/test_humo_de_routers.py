"""Toda operacion de lectura sin parametros, ejecutada al menos una vez.

## Por que existe

Auditoria del 4-sep, medida sobre los 25 routers: **19 no tenian una sola prueba
que los importara**, y sumaban **180 operaciones**. El unico que salio de esa
lista ese mismo dia fue `crm`, y salio porque al escribirle pruebas de endpoint
aparecieron **26 llamadas con la firma equivocada** que devolvian 500 —incluida
mover una tarjeta del kanban, lo unico que el modulo dejaba hacer—.

O sea que "19 routers sin pruebas de endpoint" no es una metrica de higiene: es
la misma situacion en la que estaba el CRM el dia antes de mirarlo.

Este archivo no reemplaza a las pruebas de cada modulo. Hace la comprobacion mas
barata que existe y que nadie estaba haciendo: **llamar a cada operacion de
lectura y mirar que no reviente**. Un 500 aca es un endpoint que nunca se
ejecuto.

## Que caza y que no

**Caza** todo lo que explota en el camino: firmas mal escritas, columnas que no
existen, respuestas que no serializan contra el esquema real, dependencias mal
puestas. Son los errores que no se ven leyendo el codigo y que ninguna prueba de
servicio alcanza.

**No caza** que la respuesta sea *correcta*. Un endpoint que devuelve la lista
equivocada pasa por aca sin problema. Para eso estan las pruebas de cada modulo,
y este archivo no da permiso para no escribirlas.

**Tampoco caza el aislamiento.** Corre en modo sin Clerk, donde la sesion viaja
por `X-Tenant-Id`; lo que separa una empresa de otra lo prueba
`test_aislamiento.py` contra la base real.

## Por que solo lectura

Un barrido que ejecute escrituras deja filas de basura en tablas vivas y, peor,
puede borrar. Las lecturas son seguras y son donde vive la mayoria de las 180.
"""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

#: La empresa del seed. Existe desde `db/02_seed.sql`.
EMPRESA = "a0000000-0000-0000-0000-000000000001"

#: Rutas que se saltan, cada una con su motivo. **La lista tiene que ser corta y
#: cada entrada justificarse**: es la puerta por la que se escapa lo que este
#: archivo existe para encontrar.
SALTAR = {
    # Lo llama Clerk con una firma HMAC; sin ella responde 400 y eso esta bien.
    "/api/v1/webhooks/clerk": "lo firma Clerk, no un cliente",
    # Sale a internet a consultar la BCN. Una prueba que depende de un servicio
    # ajeno falla cuando ellos tienen mantenimiento, y eso es ruido.
    "/api/v1/catalog/norms/buscar-bcn": "sale a internet",
}


def _rutas_de_lectura() -> list[str]:
    """Los `GET` que no piden parametros de ruta ni de consulta obligatorios.

    Se sacan del OpenAPI en vez de una lista escrita a mano: asi el endpoint que
    alguien agregue manana entra solo, que es justamente lo que no paso con los
    19 routers.
    """
    app.openapi_schema = None
    esquema = app.openapi()
    rutas = []
    for ruta, metodos in esquema["paths"].items():
        operacion = metodos.get("get")
        if operacion is None or ruta in SALTAR:
            continue
        if "{" in ruta:
            continue  # pide un id; no se inventa uno
        obligatorios = [
            p for p in operacion.get("parameters", []) if p.get("required")
        ]
        if obligatorios:
            continue
        rutas.append(ruta)
    return sorted(rutas)


RUTAS = _rutas_de_lectura()


@pytest.fixture(scope="module")
def cliente(request):
    """Cliente en modo sin Clerk: la sesion viaja por `X-Tenant-Id`."""
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(
            f"Sin base de datos disponible ({exc}). Esto NO comprueba que los "
            "endpoints se ejecuten: hace falta `docker compose up -d`."
        )

    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as c:
        c.headers["X-Tenant-Id"] = EMPRESA
        yield c


def test_hay_rutas_que_recorrer() -> None:
    """Si el descubrimiento se rompe, el barrido pasaria en verde sin hacer nada.

    Es la guarda contra el peor modo de fallo de este archivo: cero rutas y
    todas las pruebas en verde. Ya paso en este repositorio con un medidor que
    informo 206 titulos cuando eran 0.
    """
    assert len(RUTAS) >= 20, f"solo se descubrieron {len(RUTAS)} rutas de lectura"


@pytest.mark.parametrize("ruta", RUTAS)
def test_la_operacion_no_revienta(cliente, ruta: str) -> None:
    """**Menos de 500.** Un 4xx es una respuesta; un 500 es codigo sin ejecutar.

    403 y 401 se aceptan: en modo sin Clerk algunas guardas siguen exigiendo
    identidad, y eso es una decision, no un fallo.
    """
    respuesta = cliente.get(ruta)

    assert respuesta.status_code < 500, (
        f"GET {ruta} respondio {respuesta.status_code}. Un 5xx en una lectura "
        f"sin parametros es un endpoint que nunca se ejecuto: "
        f"{respuesta.text[:400]}"
    )


def test_una_ruta_inventada_da_404_y_no_500(cliente) -> None:
    """La otra mitad: que el barrido no pase en verde porque todo da 404.

    Sin esto, un cliente mal construido —que no llega a la aplicacion— haria
    pasar las 40 comprobaciones de arriba sin ejecutar una sola.
    """
    assert cliente.get(f"/api/v1/{uuid.uuid4().hex}").status_code == 404


def test_el_tablero_responde_de_verdad(cliente) -> None:
    """Una lectura con contenido, no solo un `200` vacio.

    El barrido de arriba se conforma con que no explote. Esta comprueba que al
    menos una operacion devuelve datos de la empresa, para que un fallo de
    configuracion que deje todo respondiendo listas vacias no pase inadvertido.
    """
    respuesta = cliente.get("/api/v1/facilities/")

    assert respuesta.status_code == 200
    assert len(respuesta.json()) > 0, (
        "La empresa del seed tiene plantas y la API devolvio cero. Suele ser "
        "RLS sin tenant declarado: la consulta no falla, devuelve nada."
    )
