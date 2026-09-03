"""Las cabeceras de seguridad salen en TODA respuesta, no solo en la feliz.

Medido el 1-sep-2026, antes de este modulo: la API no devolvia ninguna cabecera
de seguridad y anunciaba `server: uvicorn`.

## Por que estas pruebas miran las respuestas de error

Es donde se olvida. Una cabecera puesta en el endpoint sale en el 200 y no en
el 401, y justamente el 401 es la respuesta que ve alguien que esta probando la
API sin credenciales. Por eso cada comprobacion se hace sobre una ruta publica
**y** sobre una que rechaza.

## Y por que HSTS tiene sus propias pruebas

Es la unica que el navegador **recuerda**. Emitirla en desarrollo deja a quien
abra `localhost` por HTTP sin poder acceder si alguna vez entro por HTTPS al
mismo puerto, y el error no se parece en nada a la causa. Las dos pruebas
fijan las dos mitades: que no salga fuera de produccion y que si salga dentro.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.seguridad_http import SIEMPRE

#: Publica, y una que rechaza. Entre las dos cubren los dos caminos.
RUTAS = ["/health", "/api/v1/documents/"]


@pytest.fixture
def cliente():
    return TestClient(app)


class TestSalenEnTodaRespuesta:
    @pytest.mark.parametrize("ruta", RUTAS)
    @pytest.mark.parametrize("cabecera", sorted(SIEMPRE))
    def test_cada_cabecera_en_cada_ruta(self, cliente, ruta, cabecera) -> None:
        r = cliente.get(ruta)

        assert r.headers.get(cabecera) == SIEMPRE[cabecera], (
            f"{ruta} respondio {r.status_code} sin la cabecera {cabecera!r}. "
            "Las de error tambien tienen que llevarlas: son las que ve quien "
            "prueba la API sin credenciales."
        )

    def test_una_respuesta_de_error_las_lleva(self, cliente) -> None:
        """La comprobacion explicita, para que no dependa del parametro."""
        r = cliente.get("/api/v1/documents/")

        assert r.status_code == 401
        assert r.headers["X-Content-Type-Options"] == "nosniff"

    def test_una_ruta_inexistente_tambien(self, cliente) -> None:
        r = cliente.get("/api/v1/esto-no-existe")

        assert r.status_code == 404
        assert r.headers["X-Frame-Options"] == "DENY"


class TestElServidorNoSeAnuncia:
    def test_no_dice_uvicorn(self, cliente) -> None:
        """Saber que hay detras acorta el trabajo de quien busca un fallo
        conocido de esa version. No es una vulnerabilidad; es informacion que
        no hay ninguna razon para regalar."""
        assert "uvicorn" not in cliente.get("/health").headers.get("server", "").lower()

    def test_se_reemplaza_en_vez_de_borrarse(self, cliente) -> None:
        """Una respuesta sin `server` tambien dice algo: que alguien se tomo el
        trabajo de sacarla."""
        assert cliente.get("/health").headers.get("server") == "ambienta"


class TestHSTSSoloEnProduccion:
    def test_en_desarrollo_NO_se_emite(self, cliente, monkeypatch) -> None:
        """La que evita dejar a alguien sin poder abrir `localhost`."""
        monkeypatch.setattr(get_settings(), "environment", "development", raising=False)

        assert "Strict-Transport-Security" not in cliente.get("/health").headers

    def test_en_produccion_SI_se_emite(self, cliente, monkeypatch) -> None:
        monkeypatch.setattr(get_settings(), "environment", "production", raising=False)

        hsts = cliente.get("/health").headers.get("Strict-Transport-Security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts


class TestLaPoliticaNoRompeLaDocumentacion:
    """Swagger carga su estilo y su script desde un CDN — comprobado contra la
    pagina real. Una `Content-Security-Policy` con `default-src` la dejaria en
    blanco, y una documentacion rota se lee como una API rota."""

    def test_la_CSP_solo_acota_los_marcos(self, cliente) -> None:
        csp = cliente.get("/docs").headers["Content-Security-Policy"]

        assert "frame-ancestors" in csp
        assert "default-src" not in csp, (
            "Una politica con `default-src` bloquea el CDN de Swagger UI y deja "
            "`/docs` en blanco."
        )

    def test_la_documentacion_sigue_respondiendo(self, cliente) -> None:
        assert cliente.get("/docs").status_code == 200


class TestElFlagDeUvicornNoSePierde:
    """Que los dos Dockerfile lancen uvicorn con `--no-server-header`.

    ## Por que esto se comprueba leyendo un archivo y no una respuesta

    Porque **ninguna prueba de la API puede verlo**. `TestClient` no pasa por
    uvicorn: llama a la aplicacion directamente, asi que la cabecera que agrega
    el servidor no existe en las pruebas. Se descubrio consultando el sistema
    corriendo con `curl`, y la respuesta traia `server:` **dos veces** —
    `uvicorn` primero y `ambienta` despues—.

    El middleware no puede arreglarlo: uvicorn escribe la suya mas abajo, en el
    protocolo, despues de que la aplicacion termino. La unica solucion es el
    flag, y el flag vive en la configuracion del contenedor. Por eso esta
    comprobacion lee el Dockerfile: es el mismo criterio con que este
    repositorio comprueba que las migraciones esten declaradas en sus cinco
    listas.
    """

    @pytest.mark.parametrize("archivo", ["Dockerfile", "Dockerfile.dev"])
    def test_lanza_uvicorn_sin_su_cabecera(self, archivo) -> None:
        from pathlib import Path

        contenido = (Path(__file__).resolve().parents[1] / archivo).read_text(
            encoding="utf-8"
        )

        assert "--no-server-header" in contenido, (
            f"{archivo} lanza uvicorn sin `--no-server-header`, asi que la "
            "respuesta va a salir con la cabecera `server` duplicada y la "
            "primera dice `uvicorn`. Ninguna prueba de la API lo detecta: "
            "`TestClient` no pasa por el servidor."
        )
