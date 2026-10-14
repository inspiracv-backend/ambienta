"""SPEC-01 · El cliente habla con la API real."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import httpx
import pytest
import respx

from ambienta_ia.backend import (
    AlmacenamientoNoConfigurado,
    BackendCaido,
    ClienteBackend,
    SinPermiso,
)

BASE = "http://backend/api/v1"


def _norma(i: int) -> dict:
    return {"id": f"00000000-0000-0000-0000-{i:012d}", "norm_type": "ley", "norm_number": str(i),
            "title": f"Norma {i}", "updated_at": "2026-09-01T00:00:00+00:00"}


class Espera:
    def __init__(self) -> None:
        self.llamadas: list[float] = []

    async def __call__(self, s: float) -> None:
        self.llamadas.append(s)


def _cliente(espera: Espera | None = None) -> ClienteBackend:
    return ClienteBackend.con_token(BASE, "tok", dormir=espera or Espera())


def _paginas(total: int, limit: int):
    def responder(request: httpx.Request) -> httpx.Response:
        skip = int(request.url.params["skip"])
        filas = [_norma(i) for i in range(total)][skip : skip + limit]
        mas = "true" if skip + limit < total else "false"
        return httpx.Response(200, json=filas, headers={"X-Has-More": mas, "X-Page-Limit": str(limit)})

    return responder


@respx.mock
async def test_paginar_hasta_que_el_backend_diga_que_no_hay_mas():
    ruta = respx.get(f"{BASE}/catalog/norms").mock(side_effect=_paginas(24, 10))
    normas = [n async for n in _cliente().normas(limit=10)]
    assert len(normas) == 24
    assert [c.request.url.params["skip"] for c in ruta.calls] == ["0", "10", "20"]
    assert ruta.calls[-1].response.headers["X-Has-More"] == "false"


@respx.mock
async def test_una_pagina_llena_no_significa_que_haya_mas():
    ruta = respx.get(f"{BASE}/catalog/norms").mock(side_effect=_paginas(10, 10))
    normas = [n async for n in _cliente().normas(limit=10)]
    assert len(normas) == 10
    assert ruta.call_count == 1


@respx.mock
async def test_sincronizacion_incremental_con_el_maximo_visto():
    ruta = respx.get(f"{BASE}/catalog/norms").mock(side_effect=_paginas(0, 100))
    maximo = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    [n async for n in _cliente().normas(updated_since=maximo)]
    assert ruta.calls[0].request.url.params["updated_since"] == "2026-09-08T12:00:00+00:00"


@respx.mock
async def test_un_4xx_no_se_reintenta():
    ruta = respx.get(f"{BASE}/obligations/").mock(
        return_value=httpx.Response(403, json={"detail": "Falta el permiso obligation.read."})
    )
    with pytest.raises(SinPermiso) as e:
        [o async for o in _cliente().obligaciones()]
    assert ruta.call_count == 1
    assert e.value.permiso == "obligation.read"


@respx.mock
async def test_un_5xx_se_reintenta_con_espera_creciente():
    me = {"modo_desarrollo": False, "usuario": None, "empresa": None, "permisos": []}
    ruta = respx.get(f"{BASE}/me").mock(
        side_effect=[httpx.Response(502), httpx.Response(502), httpx.Response(200, json=me)]
    )
    espera = Espera()
    await _cliente(espera).yo()
    assert ruta.call_count == 3
    assert espera.llamadas == [1.0, 2.0]


@respx.mock
async def test_un_5xx_persistente_termina_en_backend_caido():
    respx.get(f"{BASE}/me").mock(return_value=httpx.Response(500))
    with pytest.raises(BackendCaido):
        await _cliente().yo()


@respx.mock
async def test_el_503_de_descarga_no_se_reintenta():
    ruta = respx.get(url__regex=r".*/download-url").mock(
        return_value=httpx.Response(503, json={"detail": "Almacenamiento no configurado"})
    )
    with pytest.raises(AlmacenamientoNoConfigurado):
        await _cliente().enlace_descarga(
            "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
        )
    assert ruta.call_count == 1


@respx.mock
async def test_el_enlace_y_su_checksum_vienen_juntos():
    respx.get(url__regex=r".*/download-url").mock(
        return_value=httpx.Response(200, json={"url": "https://s3/x", "expires_in": 300, "checksum_sha256": "9f86"})
    )
    e = await _cliente().enlace_descarga(
        "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
    )
    assert (e.url, e.expires_in, e.checksum_sha256) == ("https://s3/x", 300, "9f86")


@respx.mock
async def test_modo_desarrollo():
    ruta = respx.get(f"{BASE}/me").mock(
        return_value=httpx.Response(200, json={"modo_desarrollo": True, "usuario": None})
    )
    await ClienteBackend.modo_desarrollo(BASE, "a0000000-0000-0000-0000-000000000001").yo()
    pedido = ruta.calls[0].request
    assert pedido.headers["X-Tenant-Id"] == "a0000000-0000-0000-0000-000000000001"
    assert "Authorization" not in pedido.headers


async def test_limit_por_encima_del_maximo_es_error_de_programacion():
    with pytest.raises(ValueError):
        [n async for n in _cliente().normas(limit=501)]


def test_ningun_metodo_acepta_la_empresa():
    for nombre, metodo in inspect.getmembers(ClienteBackend, inspect.isfunction):
        if nombre.startswith("_") or nombre == "modo_desarrollo":
            continue
        parametros = inspect.signature(metodo).parameters
        assert "tenant_id" not in parametros, nombre
        assert "empresa_id" not in parametros, nombre


@respx.mock
async def test_detail_como_objeto_se_lee_como_mensaje():
    """Algunos 403 reales traen detail = {"codigo", "mensaje"}, no texto."""
    respx.get(f"{BASE}/me").mock(return_value=httpx.Response(
        403, json={"detail": {"codigo": "sesion_sin_usuario", "mensaje": "Tu cuenta no esta registrada."}}))
    with pytest.raises(SinPermiso) as e:
        await _cliente().yo()
    assert e.value.detalle == "Tu cuenta no esta registrada."
