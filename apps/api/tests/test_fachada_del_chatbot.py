"""La fachada del chatbot: la API como intermediaria del AI Service.

## Lo que estas pruebas protegen

El puente es corto y lo que puede salir mal no es que "no funcione" —eso se ve
en el primer intento— sino cuatro cosas que **funcionan igual estando mal**:

1. **Que la empresa salga del cuerpo.** Un `tenant_id` aceptado del cliente es
   un parametro con el que cualquiera elige de que empresa leer, y la peticion
   responde 200 igual. `TestLaEmpresaSaleDelToken`.
2. **Que el token no se reenvie tal cual.** Si la fachada usara un secreto
   compartido, el AI Service consultaria con alcance propio y RLS dejaria de ser
   la barrera. `TestElTokenViajaSinTransformarse`.
3. **Que una conversacion ajena se distinga de una inexistente.** Dos respuestas
   distintas son un oraculo para enumerar conversaciones de otras empresas.
   `TestUnaConversacionAjena`.
4. **Que el turno se guarde dos veces.** La persistencia es del AI Service; si
   la fachada tambien guardara, cada pregunta quedaria duplicada — y eso no se
   ve como un error, se ve como un historial raro tres semanas despues.
   `TestLaFachadaNoGuardaNada`.

## Sin red

Ninguna prueba llama al AI Service de verdad: se reemplaza `httpx` en el modulo
del servicio y se **capturan** la URL, las cabeceras y el cuerpo. Lo que se
comprueba es lo que esta API manda, que es lo unico que podemos equivocarnos
nosotros.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import ai_service as svc  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
RUTA = "/api/v1/support/chatbot/consulta"
AI = "http://ai-service-de-prueba:8100"


@pytest.fixture(scope="module")
def cliente():
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible ({exc}).")
    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def con_ai_service(monkeypatch):
    """Con `AI_SERVICE_URL` puesta, que es lo normal en un entorno con IA."""
    monkeypatch.setenv("AI_SERVICE_URL", AI)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _RespuestaFalsa:
    def __init__(self, status_code=200, cuerpo=None, texto=""):
        self.status_code = status_code
        self._cuerpo = cuerpo
        self.text = texto or json.dumps(cuerpo or {})

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin cuerpo JSON")
        return self._cuerpo


RESPUESTA_OK = {
    "conversation_id": str(uuid4()),
    "respuesta": "La Ley 19.300 exige...",
    "se_abstuvo": False,
    "citas": [],
    "guardado": True,
}


@pytest.fixture
def espia(monkeypatch):
    """Reemplaza `httpx.post` del servicio y guarda con que lo llamaron."""
    capturado: dict = {}

    def falso_post(url, json=None, headers=None, timeout=None):  # noqa: A002
        capturado["url"] = url
        capturado["cuerpo"] = json
        capturado["cabeceras"] = headers or {}
        return _RespuestaFalsa(cuerpo=RESPUESTA_OK)

    monkeypatch.setattr(svc.httpx, "post", falso_post)
    return capturado


def _uno(sql: str, empresa: str = EMPRESA_A, **params):
    with SessionLocal() as db:
        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": empresa}
        )
        return db.execute(text(sql), params).scalar()


class TestSinConfigurarLoDice:
    def test_responde_503_y_nombra_la_variable(self, cliente, monkeypatch) -> None:
        """**503 y no 500.** Mismo criterio que el almacenamiento y el correo.

        Y no cae a `localhost:8100`: en produccion eso es una conexion a nada
        que tarda en fallar, y "el chat no responde" no se parece a "falta una
        variable".
        """
        monkeypatch.setenv("AI_SERVICE_URL", "")
        get_settings.cache_clear()

        r = cliente.post(
            RUTA, headers={"X-Tenant-Id": EMPRESA_A}, json={"pregunta": "hola?"}
        )

        assert r.status_code == 503, r.text
        assert r.json()["detail"]["codigo"] == "ai_service_sin_configurar"
        assert "AI_SERVICE_URL" in r.json()["detail"]["mensaje"]
        get_settings.cache_clear()


class TestLaEmpresaSaleDelToken:
    def test_el_cuerpo_no_lleva_empresa_ni_usuario(
        self, cliente, con_ai_service, espia
    ) -> None:
        """Lo que se reenvia son los tres campos del contrato y nada mas.

        Se mandan `tenant_id` y `user_id` **a proposito**: el esquema no los
        declara, asi que Pydantic los descarta y no pueden llegar al AI Service.
        Si algun dia alguien los agregara al esquema "por comodidad", esta
        prueba lo diria.
        """
        r = cliente.post(
            RUTA,
            headers={"X-Tenant-Id": EMPRESA_A},
            json={
                "pregunta": "que me aplica?",
                "tenant_id": "a0000000-0000-0000-0000-000000000002",
                "user_id": str(uuid4()),
            },
        )

        assert r.status_code == 200, r.text
        assert set(espia["cuerpo"]) == {"pregunta"}
        assert "tenant_id" not in espia["cuerpo"]
        assert "user_id" not in espia["cuerpo"]

    def test_la_empresa_que_viaja_es_la_de_la_sesion(
        self, cliente, con_ai_service, espia
    ) -> None:
        """En desarrollo no hay token, asi que viaja `X-Tenant-Id` **derivado**.

        No el que el cliente mando en el cuerpo: el que esta API resolvio.
        """
        cliente.post(
            RUTA,
            headers={"X-Tenant-Id": EMPRESA_A},
            json={
                "pregunta": "hola?",
                "tenant_id": "a0000000-0000-0000-0000-000000000002",
            },
        )

        assert espia["cabeceras"]["X-Tenant-Id"] == EMPRESA_A


class TestElTokenViajaSinTransformarse:
    """Sobre `cabeceras()`, que es donde se decide.

    Se prueba la funcion y no el endpoint porque la suite corre en modo
    desarrollo —sin Clerk no hay token— y lo que importa comprobar es
    justamente el camino con token.
    """

    def test_con_token_va_el_bearer_original_y_no_el_tenant(self) -> None:
        h = svc.cabeceras(
            token="eyJhbGciOiJSUzI1NiJ9.el-token-de-quien-pregunta",
            tenant_id=UUID(EMPRESA_A),
            acepta="application/json",
        )

        assert h["Authorization"] == "Bearer eyJhbGciOiJSUzI1NiJ9.el-token-de-quien-pregunta"
        # **Con token no viaja `X-Tenant-Id`.** En modo produccion el AI Service
        # lo ignora, pero mandarlo igual invita a que alguien lo lea algun dia.
        assert "X-Tenant-Id" not in h

    def test_sin_token_va_el_tenant_de_la_sesion(self) -> None:
        h = svc.cabeceras(
            token=None, tenant_id=UUID(EMPRESA_A), acepta="application/json"
        )

        assert h["X-Tenant-Id"] == EMPRESA_A
        assert "Authorization" not in h

    def test_no_se_inventa_un_secreto_compartido(self) -> None:
        """La forma de la prueba importa: se comprueba que **no** haya nada mas.

        Un `X-Api-Key` o un bearer de servicio dejarian al AI Service
        consultando con alcance propio, y RLS dejaria de ser la barrera.
        """
        h = svc.cabeceras(token="t", tenant_id=UUID(EMPRESA_A), acepta="application/json")

        assert set(h) == {"Accept", "Content-Type", "Authorization"}

    def test_el_request_id_se_propaga_si_viene(self) -> None:
        h = svc.cabeceras(
            token="t", tenant_id=UUID(EMPRESA_A), acepta="x", request_id="abc-123"
        )
        assert h["X-Request-Id"] == "abc-123"


class TestElCuerpoOmiteLosOpcionalesVacios:
    def test_sin_conversacion_ni_fecha_van_solo_la_pregunta(self) -> None:
        assert svc.cuerpo(pregunta="p", conversation_id=None, fecha=None) == {"pregunta": "p"}

    def test_con_los_dos_viajan_como_cadenas(self) -> None:
        cid = uuid4()
        c = svc.cuerpo(pregunta="p", conversation_id=cid, fecha="2026-10-14")
        assert c == {"pregunta": "p", "conversation_id": str(cid), "fecha": "2026-10-14"}


class TestUnaConversacionAjena:
    def test_una_que_no_se_ve_responde_404_sin_llamar_al_ai_service(
        self, cliente, con_ai_service, espia
    ) -> None:
        """Y el 404 es el mismo que para una inexistente.

        Se usa un id inventado y no uno de la empresa B **a proposito**: la
        empresa B puede no tener conversaciones en el seed, y una prueba que se
        salta no prueba nada. Las dos entradas recorren el mismo
        `obtener_o_404` con la sesion de la empresa: lo que RLS no ve, no existe
        para ella.
        """
        r = cliente.post(
            RUTA,
            headers={"X-Tenant-Id": EMPRESA_A},
            json={"pregunta": "hola?", "conversation_id": str(uuid4())},
        )

        assert r.status_code == 404, r.text
        # Y no se reenvio nada: se autoriza **antes** de consultar.
        assert espia == {}


class TestLaFachadaNoGuardaNada:
    def test_el_turno_no_queda_escrito_dos_veces(
        self, cliente, con_ai_service, espia
    ) -> None:
        """La persistencia es del AI Service, que llama a `/support/chatbot`.

        Si la fachada tambien guardara, cada pregunta quedaria duplicada.
        """
        antes = _uno("SELECT count(*) FROM chatbot_messages")

        cliente.post(RUTA, headers={"X-Tenant-Id": EMPRESA_A}, json={"pregunta": "hola?"})

        assert _uno("SELECT count(*) FROM chatbot_messages") == antes


class TestElStreamingPasaTalCual:
    @pytest.fixture
    def ai_que_emite(self, monkeypatch):
        eventos = [
            b"event: herramienta\ndata: {\"nombre\": \"buscar_normas\"}\n\n",
            b"event: texto\ndata: {\"texto\": \"La Ley \"}\n\n",
            b"event: texto\ndata: {\"texto\": \"19.300...\"}\n\n",
            b'event: final\ndata: {"respuesta": "La Ley 19.300...", "guardado": true}\n\n',
        ]

        class _Stream:
            status_code = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b""

            def iter_raw(self):
                yield from eventos

        monkeypatch.setattr(
            svc.httpx, "stream", lambda *a, **k: _Stream()
        )
        return eventos

    def test_los_eventos_llegan_en_orden_y_sin_reinterpretar(
        self, cliente, con_ai_service, ai_que_emite
    ) -> None:
        """**Se reenvian los bytes, no una reconstruccion.**

        Rearmar los eventos a partir de lo parseado invita a perder uno
        —`herramienta`, que el frontend usa para mostrar "estoy buscando"— y a
        cambiar el orden, que es lo unico que un stream promete conservar.
        """
        with cliente.stream(
            "POST",
            RUTA,
            headers={"X-Tenant-Id": EMPRESA_A, "Accept": svc.SSE},
            json={"pregunta": "que me aplica?"},
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith(svc.SSE)
            recibido = b"".join(r.iter_bytes())

        assert recibido == b"".join(ai_que_emite)
        # El orden, explicito: `herramienta` antes del primer `texto`, y `final`
        # al cierre.
        assert recibido.index(b"herramienta") < recibido.index(b"texto")
        assert recibido.rindex(b"final") > recibido.rindex(b"texto")

    def test_el_proxy_no_puede_acumular_el_stream(
        self, cliente, con_ai_service, ai_que_emite
    ) -> None:
        """`X-Accel-Buffering: no`, o Caddy lo entrega todo junto al final.

        Un proxy que acumula convierte el streaming en una espera larga con todo
        el texto de una vez, que es exactamente lo que el streaming evita.
        """
        with cliente.stream(
            "POST",
            RUTA,
            headers={"X-Tenant-Id": EMPRESA_A, "Accept": svc.SSE},
            json={"pregunta": "hola?"},
        ) as r:
            assert r.headers["x-accel-buffering"] == "no"
            assert r.headers["cache-control"] == "no-cache"


class TestLosErroresNoFiltranNada:
    def test_un_500_del_ai_service_sale_como_503_sin_su_cuerpo(
        self, cliente, con_ai_service, monkeypatch
    ) -> None:
        """Un 500 del servicio de IA **no es un error del cliente**.

        Y su cuerpo puede traer la traza, el nombre de un host interno o el
        detalle de una consulta: no se devuelve.
        """
        traza = 'Traceback: File "/app/ambienta_ia/agente.py", line 42, clave=sk-abc123'
        monkeypatch.setattr(
            svc.httpx,
            "post",
            lambda *a, **k: _RespuestaFalsa(status_code=500, texto=traza),
        )

        r = cliente.post(RUTA, headers={"X-Tenant-Id": EMPRESA_A}, json={"pregunta": "hola?"})

        assert r.status_code == 503, r.text
        assert r.json()["detail"]["codigo"] == "ai_service_no_responde"
        assert "Traceback" not in r.text
        assert "sk-abc123" not in r.text

    def test_un_403_del_ai_service_se_conserva(
        self, cliente, con_ai_service, monkeypatch
    ) -> None:
        """Los codigos que el cliente entiende pasan con su significado.

        Traducir un 403 a 503 diria "el servicio esta caido" cuando lo que pasa
        es que a esa persona le falta un permiso.
        """
        monkeypatch.setattr(
            svc.httpx,
            "post",
            lambda *a, **k: _RespuestaFalsa(
                status_code=403, cuerpo={"mensaje": "Falta el permiso chatbot.use."}
            ),
        )

        r = cliente.post(RUTA, headers={"X-Tenant-Id": EMPRESA_A}, json={"pregunta": "hola?"})

        assert r.status_code == 403, r.text
        assert "chatbot.use" in r.json()["detail"]

    def test_si_la_red_se_cae_tambien_es_503(
        self, cliente, con_ai_service, monkeypatch
    ) -> None:
        import httpx as _httpx

        def revienta(*a, **k):
            raise _httpx.ConnectError("no se pudo resolver ai-service")

        monkeypatch.setattr(svc.httpx, "post", revienta)

        r = cliente.post(RUTA, headers={"X-Tenant-Id": EMPRESA_A}, json={"pregunta": "hola?"})

        assert r.status_code == 503, r.text
        assert "ai-service" not in r.text.lower() or "no responde" in r.text.lower()


class TestLaPreguntaSeValidaAntesDeSalir:
    @pytest.mark.parametrize("pregunta", ["", "a", "x" * 2001])
    def test_una_pregunta_fuera_de_rango_no_llega_al_ai_service(
        self, cliente, con_ai_service, espia, pregunta
    ) -> None:
        """Los limites son los del contrato del AI Service (2 a 2000).

        Validarlos aca evita un viaje y un 422 que el cliente leeria como un
        error del servicio de IA.
        """
        r = cliente.post(
            RUTA, headers={"X-Tenant-Id": EMPRESA_A}, json={"pregunta": pregunta}
        )

        assert r.status_code == 422, r.text
        assert espia == {}

    def test_una_fecha_que_no_es_de_calendario_se_rechaza(
        self, cliente, con_ai_service, espia
    ) -> None:
        """`fecha` es un dia, no una marca de tiempo.

        La vigencia de una norma es una fecha de calendario: aceptar un instante
        es la puerta de "un dia antes" que este repositorio ya sufrio tres veces.
        """
        r = cliente.post(
            RUTA,
            headers={"X-Tenant-Id": EMPRESA_A},
            json={"pregunta": "que regia?", "fecha": "2026-10-14T12:00:00Z"},
        )

        assert r.status_code == 422, r.text
        assert espia == {}
