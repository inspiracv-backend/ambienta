"""Cada recurso de negocio expone el CRUD completo, y las excepciones estan dichas.

Se empezo con 0 de 26 recursos completos y ningun DELETE en toda la API. El
hueco no era visible: hay que cruzar 60 rutas contra los metodos de cada una
para notarlo, y nadie hace eso leyendo un router.

Esta prueba lo cuenta sola. Si alguien agrega un recurso a medias, falla y dice
que le falta. Si decide a proposito no exponer una operacion, la agrega a
`SIN_CRUD_COMPLETO` con su motivo — que es la diferencia entre una decision y
un olvido.
"""
from __future__ import annotations

import re

import pytest

from app.main import app

# Operaciones que cambian de estado, no CRUD. Se excluyen del conteo porque
# `/audits/{id}/advance` no es "leer una auditoria".
SUFIJOS_DE_ACCION = (
    "/verify", "/advance", "/close", "/evaluate", "/fulfill", "/submit",
    "/stats", "/summary", "/metrics", "/audit-log", "/clerk", "/upcoming",
    "/overdue", "/generate-notifications",
)

# Recurso -> por que no tiene el CRUD entero. El motivo es la parte importante.
SIN_CRUD_COMPLETO = {
    "/catalog/norms": "la ley no se borra ni se edita a mano: se sincroniza desde la BCN",
    "/catalog/sectors": "catalogo de referencia, compartido y de solo lectura",
    "/catalog/sources": "catalogo de referencia, compartido y de solo lectura",
    "/documents/versions": "es la evidencia que respalda el cumplimiento; borrarla dejaria sin sustento a las evaluaciones que la citan",
    "/support/chatbot/messages": "borrar un mensaje suelto vuelve enganosa la conversacion",
    "/support/tickets/messages": "borrar un mensaje suelto vuelve enganosa la conversacion",
    "/tenants": "sin resolver que significa dar de baja una empresa: marcarla no impide entrar a sus usuarios, asi que hoy seria una baja que miente",
    "/support/chatbot": "una conversacion no se edita; se cierra o se retira entera",
    "/obligations/tasks": "las tareas se listan dentro de su obligacion, no sueltas",
    "/documents": "las versiones se listan dentro de su documento",
}


def _cobertura(esquema: dict) -> dict[str, set[str]]:
    recursos: dict[str, set[str]] = {}
    for ruta, metodos in esquema["paths"].items():
        if not ruta.startswith("/api/v1/") or ruta == "/api/v1":
            continue
        base = re.sub(r"/\{[^}]+\}", "/{id}", ruta)
        clave = base.replace("/{id}", "").rstrip("/")[len("/api/v1"):]
        if clave.endswith(SUFIJOS_DE_ACCION):
            continue
        tiene_id = "{id}" in base
        for metodo in metodos:
            letra = {
                "get": "R" if tiene_id else "L",
                "post": "C",
                "patch": "U",
                "put": "U",
                "delete": "D",
            }.get(metodo)
            if letra:
                recursos.setdefault(clave, set()).add(letra)
    return recursos


@pytest.fixture(scope="module")
def cobertura() -> dict[str, set[str]]:
    app.openapi_schema = None
    return _cobertura(app.openapi())


def test_los_recursos_de_negocio_tienen_crud_completo(cobertura) -> None:
    incompletos = {
        recurso: "".join(sorted({"C", "L", "R", "U", "D"} - ops))
        for recurso, ops in cobertura.items()
        if ops != {"C", "L", "R", "U", "D"} and recurso not in SIN_CRUD_COMPLETO
    }
    assert not incompletos, (
        "Recursos a medias sin motivo declarado (letra = operacion que falta; "
        f"C crear, L listar, R leer, U actualizar, D borrar): {incompletos}. "
        "Completalos, o agregalos a SIN_CRUD_COMPLETO explicando por que no."
    )


def test_las_excepciones_declaradas_siguen_existiendo(cobertura) -> None:
    """Una excepcion sobre un recurso que ya no existe es ruido que confunde."""
    fantasmas = set(SIN_CRUD_COMPLETO) - set(cobertura)
    assert not fantasmas, f"Excepciones que sobran en SIN_CRUD_COMPLETO: {fantasmas}"


def test_ninguna_excepcion_se_quedo_sin_motivo() -> None:
    vacias = [r for r, motivo in SIN_CRUD_COMPLETO.items() if not motivo.strip()]
    assert not vacias, f"Excepciones sin explicar: {vacias}"
