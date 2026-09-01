"""El transporte de correo por Resend (#122).

**Ninguna prueba de aca sale a internet.** Lo que puede tener un error nuestro
es la clasificacion de la respuesta —que 401 corte la corrida, que 422 mate el
aviso, que 429 se reintente— y eso se comprueba con respuestas simuladas. Que
Resend acepte una peticion no es algo que podamos arreglar, y una prueba que
dependa de su disponibilidad se pone roja cuando ellos tienen mantenimiento.

Para comprobar que las credenciales sirven de verdad esta
`python -m app.tareas.comprobar_correo`, que manda un correo real y se corre a
mano al configurar.
"""
from __future__ import annotations

import httpx
import pytest

from app.services import correo
from app.services.correo import (
    DE_CONFIGURACION,
    PERMANENTES,
    TransporteResend,
    esta_configurado,
    transporte_configurado,
)
from app.services.despacho import ErrorDeConfiguracion, ErrorDeEnvio, ErrorPermanente


def _respuesta(codigo: int, cuerpo: dict | str | None = None) -> httpx.Response:
    if isinstance(cuerpo, dict) or cuerpo is None:
        return httpx.Response(
            codigo,
            json=cuerpo if cuerpo is not None else {},
            request=httpx.Request("POST", correo.API),
        )
    return httpx.Response(codigo, text=cuerpo, request=httpx.Request("POST", correo.API))


@pytest.fixture
def transporte():
    return TransporteResend(
        api_key="re_de_prueba",
        remitente="Ambienta <avisos@ejemplo.cl>",
        responder_a="soporte@ejemplo.cl",
    )


def _envia(monkeypatch, transporte, respuesta):
    """Sustituye el POST y devuelve lo que se mando, ademas del resultado."""
    capturado: dict = {}

    def falso(url, **kwargs):
        capturado["url"] = url
        capturado.update(kwargs)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(correo.httpx, "post", falso)
    return capturado


class TestLaPeticion:
    def test_manda_lo_que_resend_espera(self, monkeypatch, transporte) -> None:
        capturado = _envia(monkeypatch, transporte, _respuesta(200, {"id": "re_1"}))
        transporte.enviar(
            destino="persona@empresa.cl", asunto="Vence", cuerpo="Texto", contexto={}
        )

        assert capturado["url"] == "https://api.resend.com/emails"
        cuerpo = capturado["json"]
        assert cuerpo["from"] == "Ambienta <avisos@ejemplo.cl>"
        assert cuerpo["to"] == ["persona@empresa.cl"], "Resend espera una lista"
        assert cuerpo["subject"] == "Vence"
        assert cuerpo["text"] == "Texto"
        assert cuerpo["reply_to"] == "soporte@ejemplo.cl"

    def test_la_llave_va_en_la_cabecera_y_no_en_el_cuerpo(
        self, monkeypatch, transporte
    ) -> None:
        """Una llave en el cuerpo termina en los logs del proveedor."""
        capturado = _envia(monkeypatch, transporte, _respuesta(200, {"id": "re_1"}))
        transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})

        assert capturado["headers"]["Authorization"] == "Bearer re_de_prueba"
        assert "re_de_prueba" not in str(capturado["json"])

    def test_sin_responder_a_no_se_manda_el_campo(self, monkeypatch) -> None:
        t = TransporteResend(api_key="k", remitente="A <a@b.cl>")
        capturado = _envia(monkeypatch, t, _respuesta(200, {"id": "re_1"}))
        t.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})
        assert "reply_to" not in capturado["json"], (
            "un `reply_to` vacio hace que las respuestas caigan en la nada"
        )

    def test_un_asunto_vacio_no_va_vacio(self, monkeypatch, transporte) -> None:
        capturado = _envia(monkeypatch, transporte, _respuesta(200, {"id": "re_1"}))
        transporte.enviar(destino="a@b.cl", asunto="", cuerpo="y", contexto={})
        assert capturado["json"]["subject"], "un correo sin asunto se filtra como spam"

    def test_hay_tiempo_maximo(self, monkeypatch, transporte) -> None:
        """Sin tope, el despachador queda colgado **con el candado tomado**.

        Mientras espera, ese aviso no lo puede atender nadie mas.
        """
        capturado = _envia(monkeypatch, transporte, _respuesta(200, {"id": "re_1"}))
        transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})
        assert capturado["timeout"] == correo.TIEMPO_MAXIMO
        assert capturado["timeout"] > 0


class TestLaClasificacionDelFallo:
    """La parte que puede tener un error nuestro."""

    @pytest.mark.parametrize("codigo", [401, 403])
    def test_una_llave_rechazada_corta_la_corrida(
        self, monkeypatch, transporte, codigo
    ) -> None:
        """No mata el aviso: **corta**.

        Tratarlo como permanente dejaria cada aviso encolado en `failed` en su
        primer intento, y se descubriria al arreglar la llave, cuando ya se
        perdieron.
        """
        _envia(monkeypatch, transporte, _respuesta(codigo, {"message": "invalid key"}))
        with pytest.raises(ErrorDeConfiguracion):
            transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})

    @pytest.mark.parametrize("codigo", [400, 404, 422])
    def test_un_mensaje_rechazado_no_se_reintenta(
        self, monkeypatch, transporte, codigo
    ) -> None:
        _envia(
            monkeypatch, transporte, _respuesta(codigo, {"message": "invalid to field"})
        )
        with pytest.raises(ErrorPermanente):
            transporte.enviar(destino="no-existe", asunto="x", cuerpo="y", contexto={})

    @pytest.mark.parametrize("codigo", [429, 500, 502, 503])
    def test_un_corte_se_reintenta(self, monkeypatch, transporte, codigo) -> None:
        _envia(monkeypatch, transporte, _respuesta(codigo, {"message": "slow down"}))
        with pytest.raises(ErrorDeEnvio):
            transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})

    def test_los_codigos_van_LITERALES_y_no_desde_la_constante(self) -> None:
        """Por que las dos pruebas de arriba no usan `sorted(DE_CONFIGURACION)`.

        Lo usaban, y el arnes de mutacion lo cazó: al vaciar la constante,
        `parametrize` genera **cero casos** y la prueba pasa sin ejecutar nada.
        Una prueba parametrizada sobre la constante que quiere comprobar no
        comprueba nada — se adapta a cualquier valor, incluido el vacio.

        Esta afirma la pertenencia, que es lo que la parametrizacion ya no dice.
        """
        assert DE_CONFIGURACION == {401, 403}
        assert PERMANENTES == {400, 404, 422}

    def test_429_NO_es_permanente(self, monkeypatch, transporte) -> None:
        """El limite de tasa es el caso mas facil de clasificar mal.

        Es un 4xx, asi que agrupar "los 4xx son permanentes" lo mataria — y es
        justo el fallo que **siempre** se arregla esperando.
        """
        assert 429 not in PERMANENTES
        assert 429 not in DE_CONFIGURACION

    def test_la_red_caida_se_reintenta(self, monkeypatch, transporte) -> None:
        _envia(monkeypatch, transporte, httpx.ConnectError("sin DNS"))
        with pytest.raises(ErrorDeEnvio):
            transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})

    def test_el_motivo_incluye_lo_que_dijo_resend(self, monkeypatch, transporte) -> None:
        """El codigo suelto no basta para diagnosticar de noche."""
        _envia(
            monkeypatch,
            transporte,
            _respuesta(422, {"message": "The from address is not verified"}),
        )
        with pytest.raises(ErrorPermanente, match="not verified"):
            transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})

    def test_un_cuerpo_que_no_es_json_no_revienta(self, monkeypatch, transporte) -> None:
        """Un 502 de un balanceador devuelve HTML, no JSON."""
        _envia(monkeypatch, transporte, _respuesta(502, "<html>Bad Gateway</html>"))
        with pytest.raises(ErrorDeEnvio, match="502"):
            transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})


class TestElIdentificador:
    def test_se_devuelve_el_id_de_resend(self, monkeypatch, transporte) -> None:
        _envia(monkeypatch, transporte, _respuesta(200, {"id": "re_abc123"}))
        assert (
            transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})
            == "re_abc123"
        )

    def test_una_respuesta_buena_sin_id_se_reintenta(
        self, monkeypatch, transporte
    ) -> None:
        """Sin identificador no hay como rastrear un correo que el cliente dice
        no haber recibido. Darlo por entregado perderia esa trazabilidad en
        silencio, que es peor que reintentar de mas.
        """
        _envia(monkeypatch, transporte, _respuesta(200, {}))
        with pytest.raises(ErrorDeEnvio, match="sin identificador"):
            transporte.enviar(destino="a@b.cl", asunto="x", cuerpo="y", contexto={})


class TestLaConfiguracion:
    def test_sin_llave_no_hay_transporte(self, monkeypatch) -> None:
        monkeypatch.setattr(correo, "esta_configurado", lambda: False)
        assert transporte_configurado() is None, (
            "devolver un transporte sin llave haria que cada aviso gastara sus "
            "cinco intentos antes de que nadie note que falta configuracion"
        )

    def test_hacen_falta_las_dos_cosas(self, monkeypatch) -> None:
        """Una llave sin remitente no manda nada: Resend exige `from`."""
        from app.config import Settings

        monkeypatch.setattr(
            correo, "get_settings", lambda: Settings(resend_api_key="k", correo_remitente="")
        )
        assert not esta_configurado()

        monkeypatch.setattr(
            correo, "get_settings", lambda: Settings(resend_api_key="", correo_remitente="A <a@b.cl>")
        )
        assert not esta_configurado()

        monkeypatch.setattr(
            correo,
            "get_settings",
            lambda: Settings(resend_api_key="k", correo_remitente="A <a@b.cl>"),
        )
        assert esta_configurado()

    def test_dice_QUE_falta(self, monkeypatch) -> None:
        """"No configurado" a secas obliga a adivinar cual de las dos."""
        from app.config import Settings

        monkeypatch.setattr(
            correo, "get_settings", lambda: Settings(resend_api_key="k", correo_remitente="")
        )
        assert correo._faltantes() == ["CORREO_REMITENTE"]
