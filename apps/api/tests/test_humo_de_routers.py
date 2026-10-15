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


#: Rutas que pueden responder **503 declarado** —"esta capacidad no esta
#: configurada en este entorno"— sin que eso sea un fallo, cada una con su
#: motivo. Es una lista aparte de `SALTAR` a proposito: estas **si se llaman y
#: si se ejecutan**, que es lo que este archivo mide. Lo unico que se acepta es
#: que el entorno de pruebas no tenga la variable.
CAPACIDADES_OPCIONALES = {
    "/api/v1/system/agentes-ia": (
        "la fachada del AI Service: sin `AI_SERVICE_URL` declara que falta en "
        "vez de caerse, igual que el almacenamiento y el correo. El entorno de "
        "pruebas no levanta el AI Service, y apuntarlo a un host muerto haria "
        "que el barrido esperara el timeout de conexion en cada corrida"
    ),
}


def _declara_falta_de_configuracion(respuesta) -> bool:
    """Un 503 con un `codigo` que termina en `_sin_configurar`.

    **La forma importa.** Un endpoint que revienta da 500, y uno que se cae
    contra un servicio caido da 503 con `..._no_responde`: ninguno de los dos
    entra por aca. Solo pasa la respuesta que el codigo construyo a proposito
    para decir que falta una variable.
    """
    if respuesta.status_code != 503:
        return False
    try:
        detalle = respuesta.json().get("detail")
    except ValueError:  # pragma: no cover - un 503 sin JSON no es declarado
        return False
    return isinstance(detalle, dict) and str(
        detalle.get("codigo", "")
    ).endswith("_sin_configurar")


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


def _revisar(respuesta, ruta: str) -> None:
    """La regla del barrido, **fuera de la prueba para poder medirla**.

    La guarda de abajo solo se dispara con una ruta que todavia no existe —una
    que empiece a declarar falta de configuracion sin estar en la lista—, asi
    que contra la API real no se ejecuta nunca: al mutarla, el barrido seguia
    en verde. Aca se la puede llamar con una respuesta inventada.
    """
    if _declara_falta_de_configuracion(respuesta):
        # El endpoint **se ejecuto**: llego hasta mirar su configuracion y dijo
        # que falta. Eso es una respuesta, no codigo sin correr. Pero la puerta
        # se cierra aca mismo: si manana otra ruta empieza a contestar esto, hay
        # que escribir por que.
        assert ruta in CAPACIDADES_OPCIONALES, (
            f"GET {ruta} responde 503 diciendo que le falta configuracion, y no "
            f"esta declarada en CAPACIDADES_OPCIONALES. O se configura en el "
            f"entorno de pruebas, o se agrega ahi con su motivo: "
            f"{getattr(respuesta, 'text', '')[:400]}"
        )
        return

    assert respuesta.status_code < 500, (
        f"GET {ruta} respondio {respuesta.status_code}. Un 5xx en una lectura "
        f"sin parametros es un endpoint que nunca se ejecuto: "
        f"{getattr(respuesta, 'text', '')[:400]}"
    )


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
    identidad, y eso es una decision, no un fallo. El unico 5xx que pasa es el
    503 que **declara** que falta una variable, y solo en las rutas de
    `CAPACIDADES_OPCIONALES`.
    """
    _revisar(cliente.get(ruta), ruta)


class TestElDesvioDeCapacidadSinConfigurar:
    """La excepcion al "menos de 500", medida.

    Es la unica forma de que un 5xx pase el barrido, asi que lo que importa es
    **que no se ensanche sola**: un 500 de verdad, o un 503 de un servicio
    caido, tienen que seguir cayendose.
    """

    class _Falsa:
        def __init__(self, status_code, cuerpo=None):
            self.status_code = status_code
            self._cuerpo = cuerpo

        def json(self):
            if self._cuerpo is None:
                raise ValueError("sin cuerpo")
            return self._cuerpo

    def test_un_500_nunca_entra(self) -> None:
        assert not _declara_falta_de_configuracion(self._Falsa(500))

    def test_un_503_de_servicio_caido_tampoco(self) -> None:
        """`_no_responde` es el AI Service abajo: eso **si** hay que verlo."""
        assert not _declara_falta_de_configuracion(
            self._Falsa(503, {"detail": {"codigo": "ai_service_no_responde"}})
        )

    def test_un_503_sin_cuerpo_json_tampoco(self) -> None:
        assert not _declara_falta_de_configuracion(self._Falsa(503))

    def test_un_503_con_detalle_de_texto_tampoco(self) -> None:
        """Un `detail` string es el 503 generico de FastAPI, no una declaracion."""
        assert not _declara_falta_de_configuracion(
            self._Falsa(503, {"detail": "Service Unavailable"})
        )

    def test_solo_el_que_lo_declara(self) -> None:
        assert _declara_falta_de_configuracion(
            self._Falsa(503, {"detail": {"codigo": "ai_service_sin_configurar"}})
        )

    def test_una_ruta_no_declarada_no_puede_usar_el_desvio(self) -> None:
        """La tripwire, disparada.

        Hoy ninguna ruta real entra por aca; esta prueba es la unica que
        demuestra que la puerta esta cerrada.
        """
        with pytest.raises(AssertionError, match="CAPACIDADES_OPCIONALES"):
            _revisar(
                self._Falsa(503, {"detail": {"codigo": "lo_que_sea_sin_configurar"}}),
                "/api/v1/inventada",
            )

    def test_la_ruta_declarada_si_pasa(self) -> None:
        _revisar(
            self._Falsa(503, {"detail": {"codigo": "ai_service_sin_configurar"}}),
            "/api/v1/system/agentes-ia",
        )

    def test_un_500_sigue_cayendose(self) -> None:
        with pytest.raises(AssertionError, match="nunca se ejecuto"):
            _revisar(self._Falsa(500), "/api/v1/system/agentes-ia")

    def test_ninguna_exencion_quedo_colgada(self) -> None:
        """Una ruta que se renombro deja su permiso escrito y sin dueno."""
        huerfanas = sorted(set(CAPACIDADES_OPCIONALES) - set(RUTAS))
        assert huerfanas == [], (
            "CAPACIDADES_OPCIONALES nombra rutas que el barrido ya no recorre; "
            f"sacalas: {huerfanas}"
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
