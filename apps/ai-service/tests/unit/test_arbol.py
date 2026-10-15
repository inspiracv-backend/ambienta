"""SPEC-04 · Del árbol de artículos a fragmentos citables."""

from __future__ import annotations

import uuid
from datetime import date

from ambienta_ia.backend.modelos import Articulo, Norma, VersionNorma
from ambienta_ia.sincronizar.arbol import (
    MAX_CARACTERES,
    armar_ruta,
    elegir_vigente,
    fragmentar_norma,
)

LEY = Norma(id=uuid.uuid4(), norm_type="ley", norm_number="19.300", title="Bases del Medio Ambiente",
            updated_at="2026-09-01T00:00:00Z")
V = uuid.uuid4()


def _art(tipo, numero, contenido=None, padre=None, orden=0):
    return Articulo(id=uuid.uuid4(), norm_version_id=V, parent_article_id=padre.id if padre else None,
                    article_type=tipo, article_number=numero, content=contenido, display_order=orden)


def test_la_ruta_sale_del_arbol():
    titulo = _art("titulo", "II", orden=1)
    parrafo = _art("parrafo", "2º", padre=titulo, orden=2)
    art = _art("articulo", "11", "texto", padre=parrafo, orden=3)
    por_id = {a.id: a for a in (titulo, parrafo, art)}
    assert armar_ruta(art, por_id, LEY) == "Ley 19.300 › Título II › Párrafo 2º › Artículo 11"


def test_los_contenedores_no_son_fragmentos():
    titulo = _art("titulo", "I", orden=1)
    arts = [_art("articulo", str(i), f"texto {i}", padre=titulo, orden=i + 1) for i in range(1, 4)]
    frags = fragmentar_norma(LEY, [titulo, *arts])
    assert [f.article_number for f in frags] == ["1", "2", "3"]


def test_incisos_no_se_repiten_si_el_articulo_trae_su_texto():
    art = _art("articulo", "10", "texto completo del artículo", orden=1)
    inciso = _art("inciso", "1", "texto del inciso", padre=art, orden=2)
    frags = fragmentar_norma(LEY, [art, inciso])
    assert len(frags) == 1 and frags[0].texto == "texto completo del artículo"


def test_si_el_articulo_es_solo_encabezado_se_indexan_sus_incisos_citados_por_el_articulo():
    art = _art("articulo", "10", None, orden=1)
    letras = [_art("letra", x, f"proyecto tipo {x}", padre=art, orden=i + 2) for i, x in enumerate("abc")]
    frags = fragmentar_norma(LEY, [art, *letras])
    assert {f.article_number for f in frags} == {"10"}
    assert frags[0].ruta.endswith("Artículo 10 › Letra a")


def test_un_articulo_largo_se_parte_por_parrafos_con_la_misma_identidad():
    parrafos = [f"Oración de relleno número {i}. " * 20 for i in range(6)]
    art = _art("articulo", "12", "\n\n".join(parrafos), orden=1)
    frags = fragmentar_norma(LEY, [art])
    assert len(frags) > 1
    assert {f.article_id for f in frags} == {art.id}
    assert [f.parte for f in frags] == list(range(1, len(frags) + 1))
    assert all(f.total_partes == len(frags) for f in frags)
    assert all(len(f.texto) <= MAX_CARACTERES for f in frags)


def test_dos_versiones_marcadas_vigentes_gana_la_que_empezo_despues():
    v1994 = VersionNorma(id=uuid.uuid4(), valid_from=date(1994, 3, 9), is_current=True)
    v2010 = VersionNorma(id=uuid.uuid4(), valid_from=date(2010, 1, 26), is_current=True)
    assert elegir_vigente([v1994, v2010]) is v2010


def test_valid_to_nulo_significa_que_rige():
    v = VersionNorma(id=uuid.uuid4(), valid_from=date(2000, 1, 1), valid_to=None, is_current=False)
    derogada = VersionNorma(id=uuid.uuid4(), valid_from=date(1990, 1, 1), valid_to=date(1999, 12, 31))
    assert elegir_vigente([derogada, v], hoy=date(2026, 9, 20)) is v


def test_sin_versiones_vigentes():
    derogada = VersionNorma(id=uuid.uuid4(), valid_from=date(1990, 1, 1), valid_to=date(1999, 12, 31))
    assert elegir_vigente([derogada], hoy=date(2026, 9, 20)) is None


# -- con la forma real de los datos (extracto de la Ley 19.300 del backend, 21/09/2026) ------

import json  # noqa: E402
import pathlib  # noqa: E402

from ambienta_ia.citas import numero_desde_texto  # noqa: E402

_REAL = json.loads((pathlib.Path(__file__).parent / "fixtures" / "ley19300_extracto.json").read_text())
LEY_REAL = Norma(**_REAL["norma"])
ARTS_REAL = [Articulo(**a) for a in _REAL["articulos"]]


def _por_numero(frags):
    return {f.numero_normal: f for f in frags}


def test_datos_reales_llegan_planos():
    assert not any(a.parent_article_id for a in ARTS_REAL)


def test_la_ruta_se_arma_por_orden_con_titulo_y_parrafo():
    f = _por_numero(fragmentar_norma(LEY_REAL, ARTS_REAL))["11"]
    assert f.ruta == (
        "Ley 19300 › Título II · De los Instrumentos de Gestión Ambiental"
        " › Párrafo 2° · Del Sistema de Evaluación de Impacto Ambiental › Artículo 11"
    )


def test_el_sufijo_sale_del_texto_y_no_del_article_number():
    frags = _por_numero(fragmentar_norma(LEY_REAL, ARTS_REAL))
    assert {"11", "11 bis", "11 ter", "7 bis", "7 quater", "7 quinquies"} <= set(frags)
    assert frags["11 bis"].texto.startswith("Artículo 11 bis")


def test_los_transitorios_no_pisan_a_los_permanentes():
    frags = _por_numero(fragmentar_norma(LEY_REAL, ARTS_REAL))
    assert frags["1"].texto.startswith("Artículo 1°.- El derecho a vivir")
    assert frags["1 transitorio"].texto.startswith("Artículo 1°.- El sistema de evaluación")
    assert "Artículos transitorios" in frags["1 transitorio"].ruta


def test_titulos_parrafos_y_la_fila_de_transitorios_no_son_fragmentos():
    frags = fragmentar_norma(LEY_REAL, ARTS_REAL)
    assert all(f.texto.lstrip('"').startswith("Artículo") for f in frags)
    articulos_reales = [a for a in ARTS_REAL if (a.content or "").startswith("Artículo")]
    assert len({f.article_id for f in frags}) == len(articulos_reales)


def test_numero_desde_texto():
    assert numero_desde_texto("Artículo 11 bis.- Los proponentes") == "11 bis"
    assert numero_desde_texto("Artículo 7º quáter.- La etapa") == "7 quater"
    assert numero_desde_texto("Artículo primero: Establécese la norma") == "1"
    assert numero_desde_texto("Artículo 1°.- El sistema", transitorio=True) == "1 transitorio"
    assert numero_desde_texto("Artículo Transitorio\n\nMientras no entren") == "unico transitorio"
    assert numero_desde_texto("TITULO II") is None


def test_un_considerando_corto_no_es_un_titulo():
    rca = Norma(id=uuid.uuid4(), norm_type="resolucion", norm_number="RCA-123/2019", title="RCA de prueba",
                updated_at="2026-09-21T00:00:00Z")
    a = Articulo(id=uuid.uuid4(), norm_version_id=V, article_type="article", article_number="9.2",
                 content="Considerando 9.2.- El titular deberá mantener una cortina vegetal.", display_order=1)
    [f] = fragmentar_norma(rca, [a])
    assert f.numero_normal == "9.2"
    assert f.ruta.endswith("Artículo 9.2")
