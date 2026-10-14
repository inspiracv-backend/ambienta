"""SPEC-05 · Traer lo correcto, o nada."""

from __future__ import annotations

from datetime import date

import pytest

from ambienta_ia.demo import datos as D
from ambienta_ia.recuperacion import Recuperador

pytestmark = pytest.mark.integracion


@pytest.fixture
def recuperador(catalogo_sincronizado, embeddings):
    return Recuperador(catalogo_sincronizado, embeddings, umbral=0.25, k=5)


async def test_articulo_pedido_por_numero(recuperador):
    r = await recuperador.recuperar("¿Qué dice el artículo 11 de la Ley 19.300?", D.EMPRESA_A)
    assert r.modo == "exacta"
    assert r.resultados[0].cita.articulo == "11"
    assert r.resultados[0].cita.norma == "Ley 19.300"


async def test_articulo_bis(recuperador):
    r = await recuperador.recuperar("¿qué dice el artículo 10 bis de la ley 19300?", D.EMPRESA_A)
    assert r.resultados[0].cita.articulo == "10 bis"


async def test_el_mismo_numero_en_otra_norma_se_distingue(recuperador):
    r = await recuperador.recuperar("artículo 15 del DS 40", D.EMPRESA_A)
    assert r.modo == "exacta"
    assert {x.cita.norma for x in r.resultados if "exacta" in x.origen} == {"DS 40/2012"}


async def test_pregunta_conceptual(recuperador):
    r = await recuperador.recuperar(
        "¿qué proyectos requieren un estudio de impacto ambiental?", D.EMPRESA_A
    )
    assert r.modo == "combinada"
    assert r.hay_evidencia
    assert {x.cita.articulo for x in r.resultados} & {"10", "11"}
    assert any("palabras" in x.origen for x in r.resultados)


async def test_fuera_del_corpus(recuperador):
    r = await recuperador.recuperar(
        "¿cuál es la tasa del impuesto a la renta de primera categoría?", D.EMPRESA_A
    )
    assert not r.hay_evidencia
    assert r.resultados == []


async def test_la_similitud_y_el_puntaje_son_cosas_distintas(recuperador):
    r = await recuperador.recuperar("plazo para declarar emisiones de contaminantes", D.EMPRESA_A)
    assert r.hay_evidencia
    for x in r.resultados:
        assert x.similitud is not None and x.similitud >= recuperador.umbral
        assert x.puntaje < 0.05  # RRF: del orden de 1/60


async def test_consulta_a_una_fecha(recuperador, fabrica_cliente):
    cliente = fabrica_cliente()
    r = await recuperador.recuperar(
        "artículo 11 de la Ley 19.300", D.EMPRESA_A, fecha=date(2009, 6, 30), cliente=cliente
    )
    assert r.modo == "historica"
    assert r.hay_evidencia
    assert "1994" in r.resultados[0].cita.texto


async def test_norma_sin_texto_a_esa_fecha(recuperador, fabrica_cliente):
    r = await recuperador.recuperar(
        "artículo 18 del DS 1", D.EMPRESA_A, fecha=date(1990, 1, 1), cliente=fabrica_cliente()
    )
    assert not r.hay_evidencia


async def test_sin_empresa_no_se_busca(recuperador):
    with pytest.raises(ValueError):
        await recuperador.recuperar("artículo 11", None)


class ReordenadorAnotador:
    def __init__(self, relevancia=3):
        self.preguntas: list[str] = []
        self.candidatos: list[list[str]] = []
        self.relevancia = relevancia

    async def calificar(self, pregunta, candidatos):
        self.preguntas.append(pregunta)
        self.candidatos.append([f"{c.cita.norma}:{c.cita.articulo}" for c in candidatos])
        return {c.clave: self.relevancia for c in candidatos}


async def test_con_reordenador_se_califican_las_dos_formulaciones_juntas(catalogo_sincronizado, embeddings):
    reo = ReordenadorAnotador()
    r = Recuperador(catalogo_sincronizado, embeddings, umbral=0.25, k=5, reordenador=reo)
    x = await r.recuperar("¿Qué dice el artículo 11 de la Ley 19.300?", D.EMPRESA_A,
                          alternativa="plazo para declarar emisiones de contaminantes")
    assert len(reo.preguntas) == 1  # una sola llamada al modelo
    assert "Interpretación de la consulta" in reo.preguntas[0]
    candidatos = reo.candidatos[0]
    assert "Ley 19.300:11" in candidatos and "DS 1/2013:18" in candidatos
    assert x.resultados[0].cita.articulo == "11"  # lo pedido por número y norma, primero


async def test_con_reordenador_nada_directo_es_sin_evidencia(catalogo_sincronizado, embeddings):
    r = Recuperador(catalogo_sincronizado, embeddings, umbral=0.25, k=5, reordenador=ReordenadorAnotador(2))
    x = await r.recuperar("¿qué proyectos requieren un estudio de impacto ambiental?", D.EMPRESA_A)
    assert not x.hay_evidencia and x.resultados == []


async def test_a_una_fecha_lo_pedido_por_numero_no_lo_decide_el_reordenador(catalogo_sincronizado, embeddings,
                                                                            fabrica_cliente):
    r = Recuperador(catalogo_sincronizado, embeddings, umbral=0.25, k=5, reordenador=ReordenadorAnotador(0))
    x = await r.recuperar("¿Qué decía el artículo 11 de la Ley 19.300?", D.EMPRESA_A, fecha=date(2009, 6, 30),
                          cliente=fabrica_cliente(), alternativa="artículo 11 de la Ley 19.300")
    assert x.hay_evidencia and x.modo == "historica"
    assert "1994" in x.resultados[0].cita.texto
