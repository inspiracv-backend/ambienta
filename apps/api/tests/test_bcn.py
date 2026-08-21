"""Leer normativa real de la Biblioteca del Congreso Nacional.

Estas pruebas **no salen a la red**: arman las respuestas del endpoint a mano y
verifican como se interpretan. Depender del servicio de la BCN haria que la
suite fallara cuando ellos tengan mantenimiento, que es ruido, no informacion.

Lo que se protege son las dos trampas que aparecieron al probar contra el
servicio de verdad, y que **no se ven leyendo la documentacion**:

- La fuente devuelve **filas duplicadas** por los `OPTIONAL` de la consulta.
- **Marca mas de una version como vigente.** En la Ley 19.300 estan marcadas la
  de 1994 y la de 2010; quedarse con la primera daba por vigente el texto
  original y se perdian dieciseis anos de reformas, sin ningun error a la vista.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services import bcn


def _fila(**campos) -> dict:
    """Una fila como la devuelve SPARQL: cada valor envuelto en `{"value": ...}`."""
    return {k: {"value": v} for k, v in campos.items() if v is not None}


#: La forma real que devolvio la BCN para la Ley 19.300, recortada.
#:
#: Se conserva el desorden y los duplicados **a proposito**: es lo que hace que
#: la prueba valga. Una version limpia probaria un caso que la fuente no da.
LEY_19300 = [
    _fila(version="…/19300/es@1994-03-09", fecha="1994-03-09", vigente="0"),
    _fila(version="…/19300/es@1994-03-09", fecha="1994-03-09", vigente="1"),
    _fila(version="…/19300/es@2007-10-02", fecha="2007-10-02", vigente="0"),
    _fila(version="…/19300/es@2007-03-27", fecha="2007-03-27", vigente="0"),
    _fila(version="…/19300/es@2010-11-13", fecha="2010-11-13", vigente="1"),
    _fila(version="…/19300/es@1995-02-08", fecha="1995-02-08", vigente="0"),
]


class TestLaVersionVigente:
    def test_es_la_de_fecha_mas_alta_no_la_primera_marcada(self, monkeypatch) -> None:
        """**El error que se pierde dieciseis anos de reformas.**

        La fuente marca como vigente tanto el texto de 1994 como el de 2010.
        Quedarse con la primera que aparece da por vigente el original, y no hay
        nada en la respuesta que delate el problema.
        """
        monkeypatch.setattr(bcn, "_consultar", lambda *a, **k: LEY_19300)

        versiones = bcn.versiones_de("http://ejemplo/19300")

        vigentes = [v for v in versiones if v.es_vigente]
        assert len(vigentes) == 1
        assert vigentes[0].fecha == date(2010, 11, 13)

    def test_deduplica_las_filas_repetidas(self, monkeypatch) -> None:
        """Seis filas, cinco versiones. Sin deduplicar el conteo miente."""
        monkeypatch.setattr(bcn, "_consultar", lambda *a, **k: LEY_19300)

        versiones = bcn.versiones_de("http://ejemplo/19300")

        assert len(versiones) == 5
        assert len({v.uri for v in versiones}) == 5

    def test_vienen_ordenadas_de_la_mas_vieja_a_la_mas_nueva(
        self, monkeypatch
    ) -> None:
        """La fuente las devuelve desordenadas; mostrarlas asi confunde."""
        monkeypatch.setattr(bcn, "_consultar", lambda *a, **k: LEY_19300)

        fechas = [v.fecha for v in bcn.versiones_de("http://ejemplo/19300")]

        assert fechas == sorted(fechas)
        assert fechas[-1] == date(2010, 11, 13)

    def test_avisa_si_la_fuente_no_marca_la_mas_nueva(
        self, monkeypatch, caplog
    ) -> None:
        """Si los dos criterios discrepan, la fecha manda **y queda constancia**.

        Sin el aviso, un cambio de forma en la fuente pasaria inadvertido hasta
        que alguien note que las versiones estan mal.
        """
        monkeypatch.setattr(
            bcn,
            "_consultar",
            lambda *a, **k: [
                _fila(version="v1", fecha="2020-01-01", vigente="1"),
                _fila(version="v2", fecha="2024-01-01", vigente="0"),
            ],
        )

        with caplog.at_level("WARNING"):
            versiones = bcn.versiones_de("http://ejemplo/x")

        assert versiones[-1].fecha == date(2024, 1, 1)
        assert versiones[-1].es_vigente is True
        assert "no viene marcada como vigente" in caplog.text

    def test_una_norma_sin_versiones_no_revienta(self, monkeypatch) -> None:
        monkeypatch.setattr(bcn, "_consultar", lambda *a, **k: [])
        assert bcn.versiones_de("http://ejemplo/x") == []


class TestLoQueLaFuenteDevuelveMal:
    def test_una_fecha_ilegible_no_tumba_la_corrida(self) -> None:
        """Perder una fecha es molesto; perder la sincronizacion entera por una
        norma rara es peor."""
        assert bcn._fecha("no es una fecha") is None
        assert bcn._fecha(None) is None
        assert bcn._fecha("2010-11-13") == date(2010, 11, 13)

    def test_una_version_sin_fecha_queda_al_principio(self, monkeypatch) -> None:
        """No al final: sin fecha no hay motivo para creerla la mas nueva, y
        ponerla ahi la volveria "vigente" por accidente."""
        monkeypatch.setattr(
            bcn,
            "_consultar",
            lambda *a, **k: [
                _fila(version="sin-fecha", vigente="0"),
                _fila(version="con-fecha", fecha="2024-01-01", vigente="1"),
            ],
        )

        versiones = bcn.versiones_de("http://ejemplo/x")

        assert versiones[0].fecha is None
        assert versiones[-1].es_vigente is True


class TestElMapeoDeUnaNorma:
    def test_lee_los_campos_que_importan(self, monkeypatch) -> None:
        monkeypatch.setattr(
            bcn,
            "_consultar",
            lambda *a, **k: [
                _fila(
                    norma="http://datos.bcn.cl/recurso/cl/ley/x/1994-03-09/19300",
                    titulo="APRUEBA LEY SOBRE BASES GENERALES DEL MEDIO AMBIENTE",
                    numero="19300",
                    codigo="30667",
                    publicacion="1994-03-09",
                    promulgacion="1994-03-01",
                    organismo="http://datos.bcn.cl/recurso/cl/organismo/segpres",
                    tipo="http://datos.bcn.cl/recurso/cl/norma/tipo#ley",
                )
            ],
        )

        n = bcn.buscar("medio ambiente")[0]

        assert n.numero == "19300"
        assert n.tipo == "ley"
        # El organismo llega como URI; se guarda el identificador, no la URL.
        assert n.organismo == "segpres"
        assert n.publicacion == date(1994, 3, 9)
        # `leychileCode` es **el identificador estable** de la norma en la
        # fuente: es con lo que se reconoce una norma ya importada.
        assert n.leychile_code == "30667"

    def test_una_norma_sin_numero_ni_fechas_igual_se_lee(self, monkeypatch) -> None:
        """Muchas resoluciones vienen incompletas. Descartarlas por eso perderia
        normativa real; los campos ausentes quedan en `None`."""
        monkeypatch.setattr(
            bcn,
            "_consultar",
            lambda *a, **k: [_fila(norma="http://x", titulo="ALGO", codigo="1")],
        )

        n = bcn.buscar("algo")[0]

        assert n.numero is None
        assert n.publicacion is None
        assert n.tipo == "norma"


@pytest.mark.red
class TestContraElServicioReal:
    """Se saltan por defecto: dependen de que la BCN este disponible.

    Existen igual porque **son las unicas que verifican que la consulta sigue
    siendo valida**. Las de arriba prueban como se interpreta la respuesta; esta
    prueba que la pregunta se sigue entendiendo del otro lado.

        pytest -m red
    """

    def test_la_ley_19300_llega_con_sus_versiones(self) -> None:
        normas = bcn.buscar("bases generales del medio ambiente", limite=1)
        assert normas, "La BCN no devolvio la Ley 19.300"

        n = normas[0]
        assert n.numero == "19300"

        versiones = bcn.versiones_de(n.uri)
        assert len(versiones) > 1
        assert sum(1 for v in versiones if v.es_vigente) == 1
