"""El catalogo de paises se consulta, no se administra.

La decision estaba escrita desde antes en `docs/estado-crud-base-de-datos.md`,
en una seccion titulada "conviene que este escrito para que nadie lo lea como un
olvido". Lo que fallaba es que se habia implementado a medias: sin escritura
(correcto) y **tambien sin lectura**, asi que `POST /catalog/norms` exigia un
`country_id` que la interfaz no tenia de donde sacar.

Estas comprobaciones son sobre el contrato: que la lectura exista y que la
escritura siga sin existir. Si alguien agrega un POST "por simetria", este
archivo lo detiene.
"""
from __future__ import annotations

import pytest

from app.main import app


@pytest.fixture(scope="module")
def esquema() -> dict:
    app.openapi_schema = None
    return app.openapi()


def test_se_puede_listar_paises(esquema: dict) -> None:
    assert "get" in esquema["paths"]["/api/v1/catalog/countries"]


def test_se_puede_leer_un_pais(esquema: dict) -> None:
    assert "get" in esquema["paths"]["/api/v1/catalog/countries/{country_id}"]


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_el_catalogo_de_paises_no_se_administra(esquema: dict, metodo: str) -> None:
    """Agregar un pais no es una operacion de la aplicacion.

    La lista de paises no la define un cliente ni un administrador: viene dada.
    Exponerla como editable invitaria a inventar paises y a que dos empresas
    terminaran apuntando a filas distintas del mismo lugar.
    """
    coleccion = esquema["paths"]["/api/v1/catalog/countries"]
    elemento = esquema["paths"]["/api/v1/catalog/countries/{country_id}"]

    assert metodo not in coleccion, (
        f"{metodo.upper()} /catalog/countries no deberia existir: el catalogo "
        "de paises se consulta, no se administra."
    )
    assert metodo not in elemento, (
        f"{metodo.upper()} /catalog/countries/{{id}} no deberia existir."
    )


def test_la_lectura_de_paises_no_exige_admin_global(esquema: dict) -> None:
    """Quien crea una norma necesita elegir el pais, y no siempre es admin.

    Restringirlo no protegeria nada —la lista de paises es publica— y romperia
    justo la pantalla que lo necesita.
    """
    operacion = esquema["paths"]["/api/v1/catalog/countries"]["get"]
    descripcion = str(operacion.get("description", "")) + str(operacion.get("summary", ""))
    assert "Admin Global" not in descripcion


def test_devuelve_los_campos_que_la_interfaz_necesita(esquema: dict) -> None:
    """`id` para la clave foranea, `name` para mostrar, `iso2` para la bandera."""
    componentes = esquema["components"]["schemas"]["CountryRead"]["properties"]
    for campo in ("id", "iso2", "iso3", "name", "default_timezone"):
        assert campo in componentes, f"CountryRead deberia exponer {campo}"
