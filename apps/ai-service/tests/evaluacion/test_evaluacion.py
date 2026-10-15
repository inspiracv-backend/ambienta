"""SPEC-08 · Las métricas dicen la verdad."""

from __future__ import annotations

import pathlib

import pytest

from ambienta_ia.demo import datos as D
from ambienta_ia.evaluar import (
    cargar_dataset,
    comparar_umbrales,
    evaluar_recuperacion,
    mrr,
    precision_en_k,
    recall_en_k,
)
from ambienta_ia.recuperacion import Recuperador

SEMILLA = pathlib.Path(__file__).parents[2] / "evaluacion" / "semilla_demo.jsonl"


def test_metricas_basicas():
    assert recall_en_k({"11"}, ["10", "11"], 1) == 0.0
    assert recall_en_k({"11"}, ["10", "11"], 2) == 1.0
    assert precision_en_k({"11"}, ["10", "11"], 2) == 0.5
    assert mrr({"11"}, ["10", "12", "11"]) == pytest.approx(1 / 3)


def test_el_dataset_cumple_la_forma():
    casos = cargar_dataset(SEMILLA)
    assert len(casos) >= 20
    assert sum(c.debe_abstenerse for c in casos) >= 5
    assert any(c.fecha for c in casos)


def test_un_cambio_que_empeora_no_se_mergea():
    reporte = {"falsos_positivos": 1, "detalle": [
        {"id": "fuera-renta", "debe_abstenerse": True, "hay_evidencia": True},
        {"id": "ok", "debe_abstenerse": True, "hay_evidencia": False},
    ]}
    fallas = comparar_umbrales(reporte, {"falsos_positivos": 0})
    assert fallas and "fuera-renta" in fallas[0] and "ok" not in fallas[0]


@pytest.mark.integracion
async def test_la_semilla_pasa_los_umbrales(catalogo_sincronizado, embeddings, fabrica_cliente):
    import json

    recuperador = Recuperador(catalogo_sincronizado, embeddings, umbral=0.25, k=5)
    reporte = await evaluar_recuperacion(cargar_dataset(SEMILLA), recuperador, D.EMPRESA_A, k=5,
                                         cliente=fabrica_cliente())
    umbrales = json.loads((SEMILLA.parent / "umbrales.json").read_text())["recuperacion"]
    assert comparar_umbrales(reporte, umbrales) == [], reporte


@pytest.mark.integracion
async def test_resultado_reproducible(catalogo_sincronizado, embeddings, fabrica_cliente):
    recuperador = Recuperador(catalogo_sincronizado, embeddings, umbral=0.25, k=5)
    casos = cargar_dataset(SEMILLA)
    a = await evaluar_recuperacion(casos, recuperador, D.EMPRESA_A, cliente=fabrica_cliente())
    b = await evaluar_recuperacion(casos, recuperador, D.EMPRESA_A, cliente=fabrica_cliente())
    assert a == b


@pytest.mark.integracion
async def test_evaluacion_de_respuestas_con_el_modelo_demo(catalogo_sincronizado, embeddings, fabrica_cliente):
    """El circuito completo corre sin claves. Con el modelo demo no se mide calidad de redacción."""
    import json

    from ambienta_ia.agente import Agente, RevisorNulo
    from ambienta_ia.agente.falso import ModeloDemo
    from ambienta_ia.evaluar import evaluar_respuestas
    from ambienta_ia.identidad import Sesion

    recuperador = Recuperador(catalogo_sincronizado, embeddings, umbral=0.25, k=5)
    agente = Agente(ModeloDemo(), RevisorNulo(), recuperador, embeddings)
    sesion = Sesion(tenant_id=D.EMPRESA_A, usuario_id=None, permisos=frozenset(), modo_desarrollo=True)
    reporte = await evaluar_respuestas(cargar_dataset(SEMILLA), agente, sesion, fabrica_cliente())
    umbrales = json.loads((SEMILLA.parent / "umbrales.json").read_text())["respuestas"]
    assert comparar_umbrales(reporte, umbrales) == [], {k: v for k, v in reporte.items() if k != "detalle"}
    # Lo que garantiza el circuito, con cualquier modelo: nunca responde cuando debía abstenerse.
    assert reporte["falsos_positivos"] == 0
