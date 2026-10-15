"""SPEC-10 · Adaptador SNIFA: datos abiertos de la SMA, cruzados por unidad fiscalizable."""

from __future__ import annotations

import pathlib

import psycopg
import pytest

from ambienta_ia.snifa import antecedentes, candidatas, cargar_conjunto
from ambienta_ia.snifa.descarga import archivos_de_carpeta, carpetas

pytestmark = pytest.mark.integracion

FIX = pathlib.Path(__file__).parents[1] / "unit" / "fixtures"


def _csv(nombre: str) -> bytes:
    return (FIX / nombre).read_bytes()


async def _cargar_todo(base):
    for conjunto, archivo in (("unidades", "snifa_uf.csv"), ("sancionatorios", "snifa_sancionatorios.csv"),
                              ("fiscalizaciones", "snifa_fiscalizaciones.csv")):
        await cargar_conjunto(base, conjunto, _csv(archivo))


def test_la_pagina_real_lleva_a_las_carpetas():
    html = (FIX / "snifa_datos_abiertos.html").read_text(encoding="utf-8", errors="ignore")
    c = carpetas(html)
    assert {"Sancionatorios", "Unidades Fiscalizables e Instrumentos", "Fiscalizaciones"} <= set(c)
    vista = (FIX / "snifa_carpeta_sancionatorios.html").read_text(encoding="utf-8", errors="ignore")
    assert "Sancionatorios.csv" in archivos_de_carpeta(vista)


async def test_carga_los_tres_conjuntos(base_sincronizador, base_limpia):
    await _cargar_todo(base_sincronizador)
    with psycopg.connect(base_limpia["admin"]) as c:
        u, i, s, f = (c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                      for t in ("snifa_unidad", "snifa_instrumento", "snifa_sancionatorio", "snifa_fiscalizacion"))
    assert (u, s) == (3, 7) and i > 0 and f > 0


async def test_antecedentes_de_una_unidad(base_sincronizador, base_consulta):
    await _cargar_todo(base_sincronizador)
    [a] = await antecedentes(base_consulta, [1078])
    assert a.nombre == "BARRICK - PASCUA LAMA"
    expedientes = {s["expediente"] for s in a.sancionatorios}
    assert "A-002-2013" in expedientes
    assert any(s["multa_uta"] == 7021.0 for s in a.sancionatorios)
    assert all(s["enlace"].startswith("https://snifa.sma.gob.cl/Sancionatorio/Ficha/") for s in a.sancionatorios)
    assert any(x["sigla"] == "RCA" for x in a.instrumentos)


async def test_la_misma_carga_no_se_repite(base_sincronizador):
    await _cargar_todo(base_sincronizador)
    r = await cargar_conjunto(base_sincronizador, "sancionatorios", _csv("snifa_sancionatorios.csv"))
    assert r.sin_cambios


async def test_detecta_sanciones_nuevas_y_cambios_de_estado(base_sincronizador):
    original = _csv("snifa_sancionatorios.csv").decode("latin-1")
    lineas = original.splitlines()
    await cargar_conjunto(base_sincronizador, "sancionatorios", ("\r\n".join(lineas[:-1]) + "\r\n").encode("latin-1"))
    # la última vuelve como nueva, y el proceso 1 cambia de estado
    modificado = original.replace(";En curso;27-03-2013", ";Terminado - Sanción;27-03-2013")
    r = await cargar_conjunto(base_sincronizador, "sancionatorios", modificado.encode("latin-1"))
    assert r.nuevos == [int(lineas[-1].split(";")[0])]
    assert (1, "En curso", "Terminado - Sanción") in r.cambios_de_estado


async def test_la_primera_carga_no_es_novedad(base_sincronizador):
    r = await cargar_conjunto(base_sincronizador, "sancionatorios", _csv("snifa_sancionatorios.csv"))
    assert r.nuevos == [] and r.cambios_de_estado == []


async def test_candidatas_por_nombre_y_ubicacion(base_sincronizador, base_consulta):
    await _cargar_todo(base_sincronizador)
    c = await candidatas(base_consulta, "Mall Plaza Egaña", comuna="La Reina", latitud=-33.4531, longitud=-70.5701)
    assert c and c[0]["unidad_id"] == 162
    assert c[0]["distancia_km"] is not None and c[0]["distancia_km"] < 1


async def test_la_herramienta_cruza_por_seia_y_sugiere_sin_vinculo(base_sincronizador, catalogo_sincronizado,
                                                                  embeddings, fabrica_cliente):
    from ambienta_ia.agente.evidencia import Registro
    from ambienta_ia.agente.herramientas import Herramientas
    from ambienta_ia.demo import datos as D
    from ambienta_ia.identidad import Sesion
    from ambienta_ia.observabilidad import Traza
    from ambienta_ia.recuperacion import Recuperador

    await _cargar_todo(base_sincronizador)
    sesion = Sesion(tenant_id=D.EMPRESA_A, usuario_id=None, permisos=frozenset(), modo_desarrollo=True)
    registro = Registro()
    h = Herramientas(sesion=sesion, cliente=fabrica_cliente(), recuperador=Recuperador(catalogo_sincronizado, embeddings),
                     embeddings=embeddings, registro=registro, traza=Traza())
    texto, tipo = await h.antecedentes_sma()
    assert tipo == "datos"
    norte, oficina = texto.split("## Mall Plaza Egaña")[0], texto.split("## Mall Plaza Egaña")[1]
    assert "BARRICK - PASCUA LAMA" in norte and "proyecto SEIA 1392521" in norte
    assert "A-002-2013" in norte and "7021 UTA" in norte
    assert "POSIBLES unidades fiscalizables" in oficina and "MALL PLAZA EGAÑA" in oficina
    assert registro.datos  # el revisor ve lo que devolvió


async def test_otra_empresa_no_ve_las_instalaciones_ajenas(base_sincronizador, catalogo_sincronizado, embeddings,
                                                          fabrica_cliente):
    from ambienta_ia.agente.evidencia import Registro
    from ambienta_ia.agente.herramientas import Herramientas
    from ambienta_ia.demo import datos as D
    from ambienta_ia.identidad import Sesion
    from ambienta_ia.observabilidad import Traza
    from ambienta_ia.recuperacion import Recuperador

    await _cargar_todo(base_sincronizador)
    sesion = Sesion(tenant_id=D.EMPRESA_B, usuario_id=None, permisos=frozenset(), modo_desarrollo=True)
    h = Herramientas(sesion=sesion, cliente=fabrica_cliente(tenant=D.EMPRESA_B),
                     recuperador=Recuperador(catalogo_sincronizado, embeddings), embeddings=embeddings,
                     registro=Registro(), traza=Traza())
    texto, _ = await h.antecedentes_sma()
    assert "PASCUA LAMA" not in texto and "Planta Norte" not in texto
