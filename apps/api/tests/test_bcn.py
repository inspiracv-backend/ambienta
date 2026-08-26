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


# ── Escribir en la base ───────────────────────────────────────────────────

import os  # noqa: E402
import uuid  # noqa: E402

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

#: Con el **dueno** de la base: el catalogo no lleva `tenant_id` y estas pruebas
#: adoptan y modifican normas sembradas.
URL_ADMIN = os.getenv(
    "DATABASE_ADMIN_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    engine = create_engine(URL_ADMIN)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    try:
        yield sesion
    finally:
        # Rollback siempre: se toca el catalogo global, compartido por todas
        # las empresas.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _sembrar_sin_adoptar(db, numero: str) -> None:
    """Deja en el catalogo una norma **sin identificador externo**, como el seed.

    Antes estas pruebas usaban la Ley 19.300 del seed y afirmaban que se
    adoptaba. **Dejo de funcionar en cuanto el catalogo se sincronizo de
    verdad**: la 19.300 real ya tiene su `external_norm_id`, asi que la
    sincronizacion la encuentra por ahi y no hay nada que adoptar — el resultado
    correcto, medido contra una prueba que media otra cosa.

    Es la misma leccion que ya dejo `test_perfil_empresa.py`: **una prueba que
    asume datos ajenos mide otra cosa el dia que alguien los toca.** Ahora la
    prueba pone el estado que quiere medir.
    """
    fuente = db.execute(
        text("SELECT id FROM legal_sources WHERE code = 'BCN_LEYCHILE'")
    ).scalar_one()
    pais = db.execute(
        text("SELECT id FROM countries WHERE name = 'Chile'")
    ).scalar_one()
    db.execute(
        text(
            "INSERT INTO legal_norms "
            "(country_id, source_id, norm_type, norm_number, title, status) "
            "VALUES (:p, :f, 'ley', :n, 'SEMBRADA DE PRUEBA', 'vigente')"
        ),
        {"p": pais, "f": fuente, "n": numero},
    )


def _norma(numero="19300", codigo="30667", tipo="ley", versiones=None):
    base = f"http://datos.bcn.cl/recurso/cl/{tipo}/organismo/1994-03-09/{numero}"
    return bcn.NormaBCN(
        uri=base,
        leychile_code=codigo,
        tipo=tipo,
        numero=numero,
        titulo=f"NORMA DE PRUEBA {numero}",
        organismo="segpres",
        publicacion=date(1994, 3, 9),
        promulgacion=None,
        versiones=versiones
        if versiones is not None
        else [
            bcn.VersionBCN(f"{base}/es@1994-03-09", date(1994, 3, 9), False, None, None),
            bcn.VersionBCN(f"{base}/es@2010-11-13", date(2010, 11, 13), True, None, None),
        ],
    )


class TestAdoptarLoSembrado:
    def test_no_duplica_una_norma_que_ya_estaba_con_el_mismo_numero(
        self, db: Session
    ) -> None:
        """**El error que vaciaria la matriz de todas las empresas.**

        El catalogo trae normas de ejemplo sin identificador externo. Crear una
        fila nueva al lado no solo duplica: deja `norm_sectors` —la
        clasificacion por sector, que es lo que hace funcionar el CORE— pegada a
        la copia falsa, y la norma real sin clasificar. Las matrices se vaciarian
        sin ningun error a la vista.
        """
        numero = f"PRUEBA-{uuid.uuid4().hex[:8]}"
        _sembrar_sin_adoptar(db, numero)
        antes = db.execute(
            text("SELECT count(*) FROM legal_norms WHERE norm_number = :n"),
            {"n": numero},
        ).scalar_one()

        r = bcn.sincronizar(
            db, [_norma(numero=numero, codigo=f"c{uuid.uuid4().hex[:8]}")],
            con_texto=False,
        )

        assert r.adoptadas == 1
        assert r.nuevas == 0
        despues = db.execute(
            text("SELECT count(*) FROM legal_norms WHERE norm_number = '19300'")
        ).scalar_one()
        assert despues == antes

    def test_conserva_la_clasificacion_por_sector(self, db: Session) -> None:
        """Sincronizar **no puede destruir trabajo humano.**"""
        antes = db.execute(text("SELECT count(*) FROM norm_sectors")).scalar_one()

        bcn.sincronizar(db, [_norma()], con_texto=False)

        assert db.execute(text("SELECT count(*) FROM norm_sectors")).scalar_one() == antes

    def test_le_pone_el_identificador_real_de_la_fuente(self, db: Session) -> None:
        bcn.sincronizar(db, [_norma()], con_texto=False)

        ext = db.execute(
            text("SELECT external_norm_id FROM legal_norms WHERE norm_number = '19300'")
        ).scalar_one()
        assert ext == "30667"

    def test_una_norma_que_no_estaba_se_crea(self, db: Session) -> None:
        numero = f"P{uuid.uuid4().hex[:6]}"
        r = bcn.sincronizar(db, [_norma(numero=numero, codigo=numero)], con_texto=False)

        assert r.nuevas == 1
        assert r.adoptadas == 0


class TestUnaSolaVersionVigente:
    def test_desmarca_la_que_estaba_vigente_antes(self, db: Session) -> None:
        """**Dos vigentes rompen la deteccion de matrices desactualizadas.**

        La norma sembrada traia la suya marcada; al adoptarla quedaban dos, y no
        hay contra cual comparar. Nada lo delata: las dos filas son validas.
        """
        bcn.sincronizar(db, [_norma()], con_texto=False)

        vigentes = db.execute(
            text(
                "SELECT count(*) FROM legal_norm_versions v "
                "JOIN legal_norms n ON n.id = v.norm_id "
                "WHERE n.norm_number = '19300' AND v.is_current"
            )
        ).scalar_one()
        assert vigentes == 1

    def test_sin_texto_la_vigente_es_la_mas_nueva_de_sparql(
        self, db: Session
    ) -> None:
        """Cuando no se baja el texto, SPARQL es lo unico que hay.

        **Es el camino de respaldo, no el normal.** Con el texto disponible
        manda el XML, que para la Ley 19.300 da 2024 y no 2010.
        """
        bcn.sincronizar(db, [_norma()], con_texto=False)

        etiqueta = db.execute(
            text(
                "SELECT v.version_label FROM legal_norm_versions v "
                "JOIN legal_norms n ON n.id = v.norm_id "
                "WHERE n.norm_number = '19300' AND v.is_current"
            )
        ).scalar_one()
        assert "13-11-2010" in etiqueta


class TestReimportarNoDuplica:
    def test_correrlo_dos_veces_no_agrega_nada(self, db: Session) -> None:
        """La sincronizacion va a correr sola y repetida. Si duplicara, la tabla
        crece sin techo y nadie lo nota hasta que las consultas se arrastran."""
        normas = [_norma()]
        bcn.sincronizar(db, normas)

        segunda = bcn.sincronizar(db, normas)

        assert segunda.nuevas == 0
        assert segunda.adoptadas == 0
        assert segunda.versiones_nuevas == 0


class TestLoQueSeOmiteYPorQue:
    def test_una_norma_sin_identificador_de_fuente_se_omite(self, db: Session) -> None:
        """Sin identificador estable no se la reconoce la proxima corrida, y se
        duplicaria en cada una."""
        r = bcn.sincronizar(db, [_norma(codigo="")], con_texto=False)

        assert r.nuevas == 0
        assert r.adoptadas == 0

    def test_una_version_sin_fecha_se_omite_pero_las_otras_entran(
        self, db: Session
    ) -> None:
        """`valid_from` es NOT NULL, y una version sin fecha no se puede ubicar
        en la linea de tiempo — que es para lo unico que sirve."""
        numero = f"P{uuid.uuid4().hex[:6]}"
        base = f"http://datos.bcn.cl/recurso/cl/ley/o/1994-03-09/{numero}"
        r = bcn.sincronizar(
            db,
            con_texto=False,
            normas=[
                _norma(
                    numero=numero,
                    codigo=numero,
                    versiones=[
                        bcn.VersionBCN(f"{base}/sin-fecha", None, False, None, None),
                        bcn.VersionBCN(
                            f"{base}/es@2020-01-01", date(2020, 1, 1), True, None, None
                        ),
                    ],
                )
            ],
        )

        assert r.versiones_nuevas == 1


class TestElTipoSaleDeLaUri:
    def test_una_ley_no_queda_como_resolucion(self) -> None:
        """**La Ley 19.300 no declara su tipo como `rdf:type`.**

        Solo dice `Norm` y `RootNorm`. Confiar en el tipo declarado la dejaba
        caer al valor por defecto, y la Ley de Bases Generales del Medio
        Ambiente quedaba guardada como "resolucion".
        """
        uri = "http://datos.bcn.cl/recurso/cl/ley/segpres/1994-03-09/19300"
        assert bcn._tipo_desde_uri(uri, None) == "ley"

    def test_una_resolucion_tambien_se_reconoce(self) -> None:
        uri = "http://datos.bcn.cl/recurso/cl/res/minsal/2013-10-08/2878"
        assert bcn._tipo_desde_uri(uri, None) == "res"

    def test_sin_uri_reconocible_cae_al_tipo_declarado(self) -> None:
        assert (
            bcn._tipo_desde_uri("http://otro/sitio", "http://x#res") == "res"
        )


# ── El texto desde el XML de Ley Chile ────────────────────────────────────

XML_MINIMO = """<?xml version="1.0" encoding="UTF-8"?>
<Norma xmlns="http://www.leychile.cl/esquemas" normaId="30667"
       fechaVersion="2024-04-10" derogado="no derogado">
  <EstructuraFuncional tipoParte="Título" fechaVersion="1994-03-09"
                       derogado="no derogado" transitorio="no transitorio"
                       idParte="1">
    <Texto>"TITULO I
    Disposiciones Generales</Texto>
  </EstructuraFuncional>
  <EstructuraFuncional tipoParte="Artículo" fechaVersion="2023-05-29"
                       derogado="no derogado" transitorio="no transitorio"
                       idParte="2">
    <Texto>Artículo 2°.- Para todos los efectos legales...</Texto>
  </EstructuraFuncional>
  <EstructuraFuncional tipoParte="Artículo" fechaVersion="2010-01-26"
                       derogado="derogado" transitorio="no transitorio"
                       idParte="3">
    <Texto>Artículo 5°.- Derogado.</Texto>
  </EstructuraFuncional>
  <EstructuraFuncional tipoParte="Artículo" fechaVersion="1994-03-09"
                       derogado="no derogado" transitorio="transitorio"
                       idParte="4">
    <Texto>Artículo 1° transitorio.- Mientras no se dicte...</Texto>
  </EstructuraFuncional>
</Norma>"""


class TestElTextoDeLaNorma:
    @pytest.fixture
    def texto(self, monkeypatch):
        import io as _io

        monkeypatch.setattr(
            bcn.urllib.request,
            "urlopen",
            lambda *a, **k: _io.BytesIO(XML_MINIMO.encode("utf-8")),
        )
        return bcn.descargar_texto("30667")

    def test_la_fecha_de_version_sale_del_xml(self, texto) -> None:
        """**Es la que manda sobre SPARQL.**

        Para la Ley 19.300 SPARQL dice 2010-11-13 y Ley Chile dice 2024-04-10.
        Catorce anos: marcar la de 2010 como vigente le diria a una empresa que
        cumple con un texto que ya no rige.
        """
        assert texto.fecha_version == date(2024, 4, 10)
        assert texto.derogada is False

    def test_cada_articulo_trae_su_propia_fecha(self, texto) -> None:
        """La norma no cambia entera de golpe: en la Ley 19.300 el articulo 1 es
        de 1994 y el 2 de 2023."""
        fechas = {a.numero: a.fecha_version for a in texto.articulos}
        assert fechas["Artículo 2°"] == date(2023, 5, 29)
        assert fechas["TITULO I"] == date(1994, 3, 9)

    def test_un_articulo_derogado_se_conserva_marcado(self, texto) -> None:
        """**No se descarta.** Sacarlo dejaria huecos en la numeracion y volveria
        imposible responder que decia la norma en un periodo pasado — que es
        media auditoria."""
        derogados = [a for a in texto.articulos if a.derogado]
        assert len(derogados) == 1
        assert derogados[0].numero == "Artículo 5°"

    def test_los_transitorios_se_marcan_por_el_atributo(self, texto) -> None:
        """No por el tipo: hay articulos comunes marcados como transitorios."""
        transitorios = [a for a in texto.articulos if a.tipo == "transitory"]
        assert len(transitorios) == 1
        assert "transitorio" in transitorios[0].texto

    def test_un_titulo_entrecomillado_igual_se_reconoce(self, texto) -> None:
        """Varios titulos vienen como `"TITULO I`. Sin limpiar la comilla caian
        al numero generico y el indice quedaba ilegible."""
        assert any(a.numero == "TITULO I" for a in texto.articulos)

    def test_ningun_articulo_queda_sin_numero(self, texto) -> None:
        """`article_number` es NOT NULL, y un articulo sin identificar no se
        puede citar en una auditoria."""
        assert all(a.numero for a in texto.articulos)


class TestElXmlDecideLaVigencia:
    def test_la_version_del_xml_gana_sobre_la_de_sparql(
        self, db: Session, monkeypatch
    ) -> None:
        """El caso real de la Ley 19.300, en pequeno."""
        import io as _io

        monkeypatch.setattr(
            bcn.urllib.request,
            "urlopen",
            lambda *a, **k: _io.BytesIO(XML_MINIMO.encode("utf-8")),
        )

        bcn.sincronizar(db, [_norma()])

        vigente = db.execute(
            text(
                "SELECT v.valid_from FROM legal_norm_versions v "
                "JOIN legal_norms n ON n.id = v.norm_id "
                "WHERE n.norm_number = '19300' AND v.is_current"
            )
        ).scalar_one()
        # SPARQL decia 2010-11-13; el XML dice 2024-04-10.
        assert vigente == date(2024, 4, 10)

    def test_si_el_texto_no_baja_la_norma_se_guarda_igual(
        self, db: Session, monkeypatch
    ) -> None:
        """**Perder el texto no puede perder la norma.**

        Los metadatos y el historial de versiones valen por si solos, y el texto
        se reintenta en la proxima corrida.
        """

        def revienta(*a, **k):
            raise OSError("sin red")

        monkeypatch.setattr(bcn.urllib.request, "urlopen", revienta)

        numero = f"PRUEBA-{uuid.uuid4().hex[:8]}"
        _sembrar_sin_adoptar(db, numero)

        r = bcn.sincronizar(
            db, [_norma(numero=numero, codigo=f"c{uuid.uuid4().hex[:8]}")]
        )

        assert r.con_texto == 0
        assert r.adoptadas == 1
        assert db.execute(
            text("SELECT count(*) FROM legal_norms WHERE norm_number = '19300'")
        ).scalar_one() >= 1
