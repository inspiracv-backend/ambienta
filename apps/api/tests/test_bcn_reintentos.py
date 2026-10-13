"""La consulta a la BCN reintenta un corte de red, y no una pregunta mal hecha.

Sin red: se sustituye `urlopen`. La espera tambien, para que la prueba no duerma.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from app.services import bcn


class _Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok():
    return _Respuesta(json.dumps({"results": {"bindings": [{"x": {"value": "1"}}]}}).encode())


@pytest.fixture
def red(monkeypatch):
    intentos: list[int] = []
    guion: list = []

    def urlopen(req, timeout=None):
        intentos.append(1)
        paso = guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        return paso

    monkeypatch.setattr(bcn.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(bcn.time, "sleep", lambda s: None)
    return intentos, guion


def test_un_corte_de_red_se_reintenta_y_la_consulta_sale(red) -> None:
    intentos, guion = red
    guion += [urllib.error.URLError("corte"), TimeoutError("lento"), _ok()]

    assert bcn._consultar("SELECT 1") == [{"x": {"value": "1"}}]
    assert len(intentos) == 3


def test_si_sigue_caida_el_error_sube_despues_del_ultimo_intento(red) -> None:
    intentos, guion = red
    guion += [urllib.error.URLError("caida")] * 3

    with pytest.raises(urllib.error.URLError):
        bcn._consultar("SELECT 1")
    assert len(intentos) == 1 + len(bcn.ESPERAS_ENTRE_INTENTOS)


def test_una_pregunta_rechazada_no_se_reintenta(red) -> None:
    """Un 400 da lo mismo tres veces: reintentarlo solo tapa el error con esperas."""
    intentos, guion = red
    guion += [urllib.error.HTTPError("u", 400, "Bad Request", {}, None)]

    with pytest.raises(urllib.error.HTTPError):
        bcn._consultar("SELEC mal")
    assert len(intentos) == 1


def test_un_429_si_se_reintenta(red) -> None:
    intentos, guion = red
    guion += [urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None), _ok()]

    assert bcn._consultar("SELECT 1")
    assert len(intentos) == 2
