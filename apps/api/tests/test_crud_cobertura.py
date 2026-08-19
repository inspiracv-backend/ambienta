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
    "/catalog/countries": "la lista de paises viene dada: se consulta, no se administra. Exponerla como editable invitaria a inventar paises y a que dos empresas apuntaran a filas distintas del mismo lugar",
    "/catalog/norms": "la ley no se borra ni se edita a mano: se sincroniza desde la BCN",
    "/catalog/norms/articles": "el articulado es el texto de la ley: se sincroniza desde la BCN y se lee, no se administra",
    "/catalog/sectors": "catalogo de referencia, compartido y de solo lectura",
    "/catalog/sources": "catalogo de referencia, compartido y de solo lectura",
    "/documents/versions": "es la evidencia que respalda el cumplimiento; borrarla dejaria sin sustento a las evaluaciones que la citan",
    "/support/chatbot/messages": "borrar un mensaje suelto vuelve enganosa la conversacion",
    "/support/tickets/messages": "borrar un mensaje suelto vuelve enganosa la conversacion",
    "/tenants": "sin resolver que significa dar de baja una empresa: marcarla no impide entrar a sus usuarios, asi que hoy seria una baja que miente",
    "/support/chatbot": "una conversacion no se edita; se cierra o se retira entera",
    "/obligations/tasks": "las tareas se listan dentro de su obligacion, no sueltas",
    "/documents": "las versiones se listan dentro de su documento",
    "/catalog/clasificacion/cobertura": (
        "no es un recurso: es el conteo de que normas estan clasificadas contra "
        "que sectores. Se deriva de `norm_sectors`, y se cambia clasificando "
        "normas, no editando el conteo"
    ),
    "/compliance/matrices/resumen": (
        "no es un recurso: es el conteo de la matriz desglosado por norma y por "
        "instalacion. Se calcula al leerlo, asi que no hay nada que crear ni "
        "borrar — cambia evaluando articulos, no editando el resumen"
    ),
    "/compliance/matrices/desactualizadas": (
        "no es un recurso: es una consulta derivada de comparar la version "
        "evaluada de cada norma contra la vigente. No hay nada que crear ni "
        "borrar — se resuelve publicando una version nueva o reevaluando"
    ),
    "/compliance/matrices/sincronizar": (
        "no es un recurso: es una operacion sobre la matriz. No hay una "
        "sincronizacion que listar, leer o borrar — lo que queda es su efecto "
        "sobre las normas de esa matriz"
    ),
    "/compliance/normativa-aplicable": (
        "no es un recurso: es un calculo derivado del perfil de la empresa y de "
        "la clasificacion del catalogo. No hay nada que crear, editar ni borrar "
        "— lo que se modifica son sus dos entradas"
    ),
    "/catalog/norms/sectors": (
        "una clasificacion no se crea aparte de la norma y el sector que la "
        "identifican, asi que el PUT idempotente cubre alta y edicion. Leer una "
        "suelta tampoco aplica: lo util es toda la clasificacion de esa norma, "
        "que sale del listado"
    ),
    "/users/permissions": (
        "no se crea un permiso: existen en el catalogo global. Lo que se administra "
        "es la excepcion de una persona, y el PUT es idempotente, asi que alta y "
        "edicion son la misma operacion. Leer uno suelto tampoco aplica: lo que "
        "importa es el conjunto efectivo, que sale del listado"
    ),
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
        # Cuenta como "leer uno" solo si el ULTIMO segmento es el parametro.
        # Un recurso anidado como `/audits/{id}/participants` lleva parametro
        # del PADRE y aun asi es un listado; mirar si el path contiene `{id}`
        # en cualquier posicion los clasificaba mal a todos.
        tiene_id = base.rstrip("/").endswith("{id}")
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
