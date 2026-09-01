"""Paginacion acotada, y que nunca corte en silencio (#167).

## Lo que se medio contra el contrato en ejecucion

| Hallazgo | Antes |
|---|---|
| `limit` sin tope maximo | **25 de 25** endpoints que lo exponen |
| Truncamiento silencioso | 100 filas de 340, y el cliente sin forma de saberlo |

**El truncamiento silencioso es el peor de los dos, y es mas enganoso que no
paginar**: una pantalla que muestra 100 filas de 340 se ve perfectamente normal.
Nadie la reporta, porque no hay nada que se vea mal.

## Lo que estas pruebas protegen

1. **Que ningun endpoint acepte un tamano arbitrario.** `limit=100000` tiene que
   ser un 422, no una consulta que barre la tabla.
2. **Que la cabecera diga la verdad en los dos sentidos.** `X-Has-More: true`
   cuando falta y `false` cuando no: una que solo aparece cuando falta algo
   obliga a distinguir "no hay mas" de "esta version no lo dice".
3. **Que la fila de sobra no se escape al cuerpo.** Se piden `limit + 1` para
   saber si hay mas; devolver esa fila daria paginas de `limit + 1` y duplicaria
   un registro en la pagina siguiente.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from app.main import app  # noqa: E402  (despues de fijar DATABASE_URL)
from app.routers._paginacion import (  # noqa: E402
    POR_DEFECTO,
    TOPE_DE_PAGINA,
    Pagina,
    recortar,
)

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"

#: Un listado de empresa cualquiera sirve: lo que se comprueba es la
#: paginacion, que es la misma en los 25.
RUTA = "/api/v1/iso14001/aspects"


@pytest.fixture(scope="module")
def cliente():
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        engine.connect().close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    engine.dispose()
    return TestClient(app)


def _como_a() -> dict[str, str]:
    return {"X-Tenant-Id": EMPRESA_A}


class TestElTopeEsDeVerdad:
    def test_pedir_cien_mil_filas_se_RECHAZA(self, cliente) -> None:
        """"El servidor nunca debe permitir una consulta arbitraria del
        cliente" — y antes se la daba en 25 de 25 endpoints."""
        r = cliente.get(f"{RUTA}?limit=100000", headers=_como_a())

        assert r.status_code == 422, r.text

    def test_el_mensaje_dice_cual_es_el_maximo(self, cliente) -> None:
        """Un tope que solo vive en el codigo obliga a descubrirlo probando."""
        r = cliente.get(f"{RUTA}?limit=100000", headers=_como_a())

        assert str(TOPE_DE_PAGINA) in r.text

    def test_justo_EN_el_tope_se_acepta(self, cliente) -> None:
        """El borde: `le`, no `lt`. Y es lo que impide "arreglar" el rechazo
        bajando el tope hasta que nada pase."""
        r = cliente.get(f"{RUTA}?limit={TOPE_DE_PAGINA}", headers=_como_a())

        assert r.status_code == 200, r.text

    def test_el_frontend_de_hoy_sigue_funcionando(self, cliente) -> None:
        """Las tres pantallas ISO piden `limit=500`.

        El tope se eligio para no romperlas: bajarlo seria romper lo que
        funciona hoy por un numero elegido a ojo.
        """
        r = cliente.get(f"{RUTA}?limit=500", headers=_como_a())

        assert r.status_code == 200, r.text

    def test_un_limit_de_cero_o_negativo_se_rechaza(self, cliente) -> None:
        """Pedir cero filas no es una pagina, es una consulta sin sentido."""
        assert cliente.get(f"{RUTA}?limit=0", headers=_como_a()).status_code == 422
        assert cliente.get(f"{RUTA}?limit=-5", headers=_como_a()).status_code == 422

    def test_un_skip_negativo_tambien(self, cliente) -> None:
        assert cliente.get(f"{RUTA}?skip=-1", headers=_como_a()).status_code == 422

    def test_el_tope_esta_en_el_OPENAPI(self, cliente) -> None:
        """Para que se descubra leyendo, no probando."""
        esquema = cliente.get("/openapi.json").json()
        parametros = esquema["paths"][RUTA]["get"]["parameters"]
        limite = next(p for p in parametros if p["name"] == "limit")

        assert limite["schema"]["maximum"] == TOPE_DE_PAGINA


class TestLaCabeceraNoMiente:
    def test_dice_que_NO_hay_mas_cuando_no_lo_hay(self, cliente) -> None:
        """Va siempre, tambien cuando no falta nada.

        Una cabecera que solo aparece cuando hay mas obliga a distinguir "no hay
        mas" de "esta version del servidor no lo dice", y son cosas distintas.
        """
        r = cliente.get(f"{RUTA}?limit={TOPE_DE_PAGINA}", headers=_como_a())

        assert r.headers["X-Has-More"] == "false"

    def test_dice_que_SI_hay_mas_cuando_lo_hay(self, cliente) -> None:
        """La afirmacion central de #167.

        Con `limit=1` sobre una empresa que tiene mas de un aspecto, la
        respuesta trae uno y **lo dice**. Antes traia uno y se veia igual que
        si fuera el unico.
        """
        cuantos = len(cliente.get(f"{RUTA}?limit=500", headers=_como_a()).json())
        if cuantos < 2:
            pytest.skip("La empresa no tiene suficientes aspectos para cortar")

        r = cliente.get(f"{RUTA}?limit=1", headers=_como_a())

        assert len(r.json()) == 1
        assert r.headers["X-Has-More"] == "true"

    def test_la_fila_de_sobra_NO_se_escapa_al_cuerpo(self, cliente) -> None:
        """Se piden `limit + 1` para saber si hay mas.

        Si esa fila se devolviera, cada pagina traeria `limit + 1` registros y
        el ultimo saldria otra vez al principio de la siguiente — un duplicado
        que en una lista de incumplimientos se lee como dos hallazgos.
        """
        cuantos = len(cliente.get(f"{RUTA}?limit=500", headers=_como_a()).json())
        if cuantos < 3:
            pytest.skip("La empresa no tiene suficientes aspectos para cortar")

        assert len(cliente.get(f"{RUTA}?limit=2", headers=_como_a()).json()) == 2

    def test_la_cabecera_repite_el_limite_aplicado(self, cliente) -> None:
        """Para que el cliente no tenga que suponer cual se uso cuando no
        mando ninguno."""
        r = cliente.get(RUTA, headers=_como_a())

        assert r.headers["X-Page-Limit"] == str(POR_DEFECTO)


class TestRecortar:
    """La funcion suelta, sin HTTP: los bordes son mas faciles de fijar aca."""

    class _Respuesta:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

    def test_con_una_fila_de_sobra_marca_que_hay_mas(self) -> None:
        r = self._Respuesta()
        pagina = Pagina(skip=0, limit=2)

        devuelto = recortar(r, [1, 2, 3], pagina)

        assert devuelto == [1, 2]
        assert r.headers["X-Has-More"] == "true"

    def test_con_exactamente_el_limite_NO_marca_que_hay_mas(self) -> None:
        """El borde de fuera por uno.

        Con `>=` en vez de `>` una pagina exacta diria que hay mas y la
        pantalla ofreceria una pagina siguiente vacia.
        """
        r = self._Respuesta()
        pagina = Pagina(skip=0, limit=2)

        devuelto = recortar(r, [1, 2], pagina)

        assert devuelto == [1, 2]
        assert r.headers["X-Has-More"] == "false"

    def test_con_menos_que_el_limite_tampoco(self) -> None:
        r = self._Respuesta()

        assert recortar(r, [1], Pagina(skip=0, limit=2)) == [1]
        assert r.headers["X-Has-More"] == "false"

    def test_sin_filas_no_revienta(self) -> None:
        r = self._Respuesta()

        assert recortar(r, [], Pagina(skip=0, limit=2)) == []
        assert r.headers["X-Has-More"] == "false"

    def test_se_pide_exactamente_una_fila_de_mas(self) -> None:
        """Ni dos, que traeria de mas; ni ninguna, que no delataria nada."""
        assert Pagina(skip=0, limit=100).pedir == 101


class TestTodosLosListadosQuedaronAcotados:
    def test_ningun_endpoint_acepta_un_limit_sin_maximo(self, cliente) -> None:
        """La afirmacion que cubre los 25 a la vez.

        Escrita sobre el OpenAPI y no sobre el codigo: lo que importa es lo que
        el servidor **acepta**, no como esta escrito. Un endpoint nuevo sin tope
        cae aca sin que nadie tenga que acordarse de agregarlo a una lista.
        """
        esquema = cliente.get("/openapi.json").json()

        sin_tope: list[str] = []
        for ruta, metodos in esquema["paths"].items():
            for metodo, operacion in metodos.items():
                for parametro in operacion.get("parameters", []):
                    if parametro["name"] != "limit":
                        continue
                    if "maximum" not in parametro.get("schema", {}):
                        sin_tope.append(f"{metodo.upper()} {ruta}")

        assert not sin_tope, (
            "Estos listados aceptan un tamano de pagina arbitrario: "
            f"{sin_tope}. Usa la dependencia `paginacion` de `_paginacion.py`."
        )

    def test_hay_listados_paginados_que_comprobar(self, cliente) -> None:
        """Y esto es lo que impide que la de arriba pase por estar vacia.

        Si un cambio quitara `limit` de todos los endpoints, la comprobacion
        anterior seguiria en verde sin comprobar nada.
        """
        esquema = cliente.get("/openapi.json").json()

        con_limit = [
            f"{m} {ruta}"
            for ruta, metodos in esquema["paths"].items()
            for m, op in metodos.items()
            for p in op.get("parameters", [])
            if p["name"] == "limit"
        ]

        assert len(con_limit) >= 20, f"solo {len(con_limit)} listados con `limit`"
