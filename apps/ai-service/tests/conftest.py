"""
Fixtures compartidas.

Las pruebas de integración necesitan PostgreSQL con pgvector. Por defecto usan el contenedor
del README (`localhost:55432`); se cambia con TEST_DATABASE_URL. Si no hay base, se saltan.
Cada sesión de pruebas crea una base nueva y la borra al terminar.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator

import httpx
import psycopg
import pytest

from ambienta_ia.backend import ClienteBackend
from ambienta_ia.conocimiento import BaseConocimiento, abrir_base
from ambienta_ia.conocimiento.migrar import migrar
from ambienta_ia.demo import datos as D
from ambienta_ia.demo.backend_simulado import Estado, crear_app
from ambienta_ia.proveedores import EmbeddingsLocales

URL_ADMIN = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:ambienta@localhost:55432/postgres")
DIMENSION = 256
CLAVE = "clave-de-prueba"
BACKEND = "http://backend/api/v1"


async def _sin_espera(_: float) -> None:
    return None


@pytest.fixture
def estado_backend() -> Estado:
    return Estado()


@pytest.fixture
def transporte(estado_backend: Estado) -> httpx.ASGITransport:
    return httpx.ASGITransport(app=crear_app(estado_backend))


@pytest.fixture
def fabrica_cliente(transporte):
    """Clientes contra el backend simulado, sin red y sin esperas reales entre reintentos."""

    def hacer(*, tenant=D.EMPRESA_A, token: str | None = None) -> ClienteBackend:
        opciones = {"transporte": transporte, "dormir": _sin_espera}
        if token:
            return ClienteBackend.con_token(BACKEND, token, **opciones)
        return ClienteBackend.modo_desarrollo(BACKEND, tenant, **opciones)

    return hacer


@pytest.fixture
def embeddings() -> EmbeddingsLocales:
    return EmbeddingsLocales(dimension=DIMENSION)


def _url(base: str, usuario: str | None = None, clave: str | None = None, db: str | None = None) -> str:
    info = psycopg.conninfo.conninfo_to_dict(base)
    if usuario:
        info["user"] = usuario
        info["password"] = clave
    if db:
        info["dbname"] = db
    return psycopg.conninfo.make_conninfo(**info)


@pytest.fixture(scope="session")
def base_de_prueba() -> Iterator[dict[str, str]]:
    try:
        with psycopg.connect(URL_ADMIN, autocommit=True, connect_timeout=3) as c:
            nombre = f"ambienta_ia_prueba_{uuid.uuid4().hex[:8]}"
            c.execute(f'CREATE DATABASE "{nombre}"')
    except psycopg.OperationalError:
        pytest.skip("No hay PostgreSQL con pgvector (TEST_DATABASE_URL)")
    admin = _url(URL_ADMIN, db=nombre)
    migrar(admin, dimension=DIMENSION, clave_consulta=CLAVE, clave_sincronizador=CLAVE)
    yield {
        "admin": admin,
        "consulta": _url(admin, "ia_consulta", CLAVE),
        "sincronizador": _url(admin, "ia_sincronizador", CLAVE),
    }
    with psycopg.connect(URL_ADMIN, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')


@pytest.fixture
def base_limpia(base_de_prueba) -> dict[str, str]:
    with psycopg.connect(base_de_prueba["admin"], autocommit=True) as c:
        c.execute("TRUNCATE fragmento, version_norma, sincronizacion, snifa_unidad, snifa_instrumento, "
                  "snifa_sancionatorio, snifa_fiscalizacion, snifa_carga CASCADE")
    return base_de_prueba


@pytest.fixture
async def base_sincronizador(base_limpia) -> AsyncIterator[BaseConocimiento]:
    b = await abrir_base(base_limpia["sincronizador"], maximo=2)
    yield b
    await b.cerrar()


@pytest.fixture
async def base_consulta(base_limpia) -> AsyncIterator[BaseConocimiento]:
    b = await abrir_base(base_limpia["consulta"], maximo=4)
    yield b
    await b.cerrar()


@pytest.fixture
async def catalogo_sincronizado(fabrica_cliente, base_sincronizador, base_consulta, embeddings):
    """La base con el catálogo del backend simulado ya indexado."""
    from ambienta_ia.sincronizar import sincronizar

    cliente = fabrica_cliente()
    r = await sincronizar(cliente, base_sincronizador, embeddings)
    await cliente.cerrar()
    assert not r.errores
    return base_consulta
