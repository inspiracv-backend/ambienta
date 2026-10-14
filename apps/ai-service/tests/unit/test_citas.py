"""SPEC-05 · Cómo se nombra una norma y un artículo."""

import pytest

from ambienta_ia.citas import detectar_cita, etiqueta_norma, normalizar_norma, numero_normal


@pytest.mark.parametrize(
    "texto,clave",
    [
        ("DS 40", "ds/40"),
        ("D.S. N° 40", "ds/40"),
        ("decreto supremo 40", "ds/40"),
        ("Ley 19.300", "ley/19300"),
        ("ley N°19300", "ley/19300"),
        ("decreto_supremo 40/2012", "ds/40"),
        ("resolucion_exenta 123/2019", "res/123"),
        ("DFL 725", "dfl/725"),
    ],
)
def test_variantes_del_nombre_de_una_norma(texto, clave):
    assert normalizar_norma(texto) == clave


def test_sin_numero_no_hay_norma():
    assert normalizar_norma("la ley ambiental") is None


def test_articulo_y_norma():
    c = detectar_cita("¿Qué dice el artículo 11 de la Ley 19.300?")
    assert (c.articulo, c.norma) == ("11", "ley/19300")


def test_articulo_bis():
    assert detectar_cita("¿qué dice el artículo 10 bis?").articulo == "10 bis"


def test_articulo_transitorio_y_abreviado():
    assert detectar_cita("art. 1° transitorio").articulo == "1 transitorio"
    assert detectar_cita("el art 15 del DS 40").articulo == "15"
    assert detectar_cita("el art 15 del DS 40").norma == "ds/40"


def test_el_numero_de_articulo_no_se_lee_como_norma():
    assert detectar_cita("artículo 11").norma is None


def test_pregunta_sin_cita():
    assert not detectar_cita("¿qué proyectos requieren estudio de impacto ambiental?")


def test_numero_normal():
    assert numero_normal("10 bis", "articulo") == "10 bis"
    assert numero_normal("1°", "transitorio") == "1 transitorio"
    assert numero_normal("Artículo 11", "articulo") == "11"


def test_etiqueta():
    assert etiqueta_norma("ley", "19.300", "x") == "Ley 19.300"
    assert etiqueta_norma("decreto_supremo", "40/2012", "x") == "DS 40/2012"
    assert etiqueta_norma("ley", None, "Título") == "Título"
