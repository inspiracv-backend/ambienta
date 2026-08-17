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


def test_toda_operacion_tiene_titulo_propio(esquema: dict) -> None:
    """Ninguna operacion se queda con el "List Audits" que FastAPI inventa.

    Ese texto es el nombre de la funcion de Python con espacios: describe el
    codigo, no lo que hace el endpoint para quien lo consume. En /docs deja 206
    entradas que hay que abrir una por una para entender.
    """
    from app.main import app
    from app.openapi import _summaries_por_defecto

    por_defecto = _summaries_por_defecto(app)
    # `/health` y la raiz de la version se documentan a mano; no son recursos.
    exentas = {("/health", "get"), ("/health/db", "get"), ("/api/v1", "get")}

    genericas = [
        f"{metodo.upper()} {ruta}"
        for ruta, metodo, op in operaciones(esquema)
        if (ruta, metodo) not in exentas
        and op.get("summary") == por_defecto.get((ruta, metodo))
    ]
    assert not genericas, f"Con el titulo por defecto de FastAPI: {genericas}"


def test_toda_operacion_explica_que_hace(esquema: dict) -> None:
    """Un titulo sin explicacion no alcanza para integrar sin preguntar."""
    mudas = [
        f"{metodo.upper()} {ruta}"
        for ruta, metodo, op in operaciones(esquema)
        if not (op.get("description") or "").strip()
    ]
    assert not mudas, f"Sin descripcion: {mudas}"


def test_el_422_dice_que_detail_es_una_lista(esquema: dict) -> None:
    """No basta con que el 422 exista: FastAPI ya lo pone, y no explica nada.

    Su texto por defecto es "Validation Error" y su ejemplo, ninguno. Lo que
    hay que decir es que en este caso `detail` llega como **lista** y no como
    texto — el frontend ya mostro `[object Object]` por asumir lo contrario.

    Por eso se afirma sobre el contenido y no sobre la presencia de la clave:
    comprobar que "422" existe pasaria igual con el default, y seria un test
    que no protege nada.
    """
    sin_explicar = [
        f"{metodo.upper()} {ruta}"
        for ruta, metodo, op in operaciones(esquema)
        if op.get("requestBody")
        and "lista" not in op.get("responses", {}).get("422", {}).get("description", "")
    ]
    assert not sin_explicar, f"Con el 422 generico de FastAPI: {sin_explicar}"


def test_el_texto_escrito_a_mano_le_gana_al_derivado(esquema: dict) -> None:
    """La derivacion rellena huecos; no pisa a quien explico mejor.

    `DELETE /users/{id}` tiene una explicacion propia sobre la diferencia
    entre suspender y retirar. Si la derivacion la reemplazara por su frase
    generica, se perderia justo el matiz que costo escribir.
    """
    op = esquema["paths"]["/api/v1/users/{user_id}"]["delete"]
    assert "suspender" in op["description"]


def test_la_descripcion_no_promete_una_barrera_que_no_existe(esquema: dict) -> None:
    """RLS es la unica barrera, no la segunda (CLAUDE.md §4).

    Decir "segunda barrera" sugiere que la aplicacion tambien filtra por
    `tenant_id`, y no lo hace: ni `CRUDBase` ni un solo router. Quien integre
    creyendo que hay dos redes puede confiarse de una que no esta.
    """
    descripcion = esquema["info"]["description"]
    # Se busca la forma *afirmativa*, que es la equivocada. Negarla —"no es la
    # segunda barrera: es la unica"— es justamente el texto correcto, asi que
    # prohibir la frase suelta rechazaria la version buena.
    assert "Es una segunda barrera" not in descripcion
    assert "es la unica" in descripcion


def test_la_descripcion_explica_el_claim_tenant_id(esquema: dict) -> None:
    """Es lo que mas caro costo descubrir: el token de sesion no lo trae.

    Que este escrito en el contrato es la diferencia entre leerlo y perder una
    tarde probando.
    """
    descripcion = esquema["info"]["description"]
    assert "tenant_id" in descripcion
    assert "template" in descripcion
