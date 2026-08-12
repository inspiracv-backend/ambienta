"""El contrato OpenAPI describe como fallan los endpoints, no solo como aciertan.

Estas comprobaciones existen porque el hueco se abre solo: alguien agrega un
router, FastAPI lo documenta con su camino feliz, y el 401 y el 404 no
aparecen por ningun lado. Como las reglas se derivan de la ruta, un endpoint
nuevo las hereda — y si alguien rompe esa derivacion, estos tests lo dicen.
"""
from __future__ import annotations

import pytest

from app.main import app

METODOS = ("get", "post", "patch", "put", "delete")


@pytest.fixture(scope="module")
def esquema() -> dict:
    # `app.openapi()` cachea en `app.openapi_schema`; se limpia para que el
    # test mida lo que construye el codigo y no una copia de otro test.
    app.openapi_schema = None
    return app.openapi()


def operaciones(esquema: dict):
    for ruta, metodos in esquema["paths"].items():
        for metodo, operacion in metodos.items():
            if metodo in METODOS:
                yield ruta, metodo, operacion


def test_toda_operacion_autenticada_declara_401(esquema: dict) -> None:
    """Si un endpoint exige token, tiene que decir que pasa sin el."""
    faltantes = [
        f"{metodo.upper()} {ruta}"
        for ruta, metodo, op in operaciones(esquema)
        if op.get("security") and "401" not in op.get("responses", {})
    ]
    assert not faltantes, f"Sin 401 documentado: {faltantes}"


def test_toda_operacion_con_id_declara_404(esquema: dict) -> None:
    """Si un endpoint recibe un id, ese id puede no existir."""
    faltantes = [
        f"{metodo.upper()} {ruta}"
        for ruta, metodo, op in operaciones(esquema)
        if "{" in ruta and "404" not in op.get("responses", {})
    ]
    assert not faltantes, f"Sin 404 documentado: {faltantes}"


def test_el_webhook_no_pide_bearer(esquema: dict) -> None:
    """Quien llama es Clerk, no un usuario: se valida la firma HMAC.

    Si algun dia aparece con `security`, es que se le colgo la dependencia de
    sesion y Clerk dejaria de poder entregarnos eventos.
    """
    webhook = [
        op for ruta, _, op in operaciones(esquema) if "webhook" in ruta
    ]
    assert webhook, "Se esperaba al menos un endpoint de webhook"
    assert all(not op.get("security") for op in webhook)


def test_todo_tag_usado_tiene_descripcion(esquema: dict) -> None:
    """Un tag sin descripcion deja una seccion muda en /docs."""
    descritos = {t["name"] for t in esquema.get("tags", [])}
    usados = {
        tag
        for _, _, op in operaciones(esquema)
        for tag in op.get("tags", [])
    }
    assert not (usados - descritos), f"Tags sin describir: {usados - descritos}"


def test_el_esquema_de_error_existe(esquema: dict) -> None:
    """Las respuestas de error apuntan a `DetalleError`; tiene que estar."""
    assert "DetalleError" in esquema["components"]["schemas"]


def test_la_descripcion_explica_el_claim_tenant_id(esquema: dict) -> None:
    """Es lo que mas caro costo descubrir: el token de sesion no lo trae.

    Que este escrito en el contrato es la diferencia entre leerlo y perder una
    tarde probando.
    """
    descripcion = esquema["info"]["description"]
    assert "tenant_id" in descripcion
    assert "template" in descripcion
