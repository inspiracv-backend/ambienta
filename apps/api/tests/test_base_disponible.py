"""Que la base este de verdad ahi cuando CI dice que las pruebas pasaron.

## El hueco

**34 archivos de prueba se saltan solos si no pueden conectarse a la base.**
Es lo correcto en un portatil: nadie deberia tener que levantar Postgres para
corregir una funcion pura, y una suite que falla por eso se vuelve ruido.

Pero un `skip` **sale con codigo 0**. Si el servicio de Postgres de CI no
levanta —cambio de imagen, puerto ocupado, healthcheck que se queda corto— las
34 se saltan, pytest informa exito y el job queda **verde sobre cero cobertura
de base**. Y justo ahi vive lo que este repositorio protege: el aislamiento
multi-tenant, las claves foraneas que no pasan por RLS, los CHECK.

Medido: con Postgres apagado, `pytest tests/test_equipos_vencimientos.py`
imprime `ssssssssssssssss` y sale con **exit 0**.

Es exactamente la categoria que CLAUDE.md llama "los medidores tambien pueden
mentir, y es peor": una prueba falsa falla una vez; un verde falso se cita
despues como un hecho.

## Lo que hace esta prueba

En CI —donde `CI` viene puesta por GitHub Actions— **exige** que la base
responda, y falla ruidosamente si no. En un portatil se salta como las demas.

Es la unica prueba del repositorio que se comporta distinto segun el entorno, y
tiene que serlo: lo que comprueba es una propiedad *del entorno*, no del codigo.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

#: GitHub Actions la define en `true` en cada job. Tambien la ponen GitLab,
#: CircleCI y Travis, asi que no ata el repositorio a un proveedor.
EN_CI = os.getenv("CI", "").lower() in {"1", "true", "yes"}


def _error_de_conexion() -> str | None:
    """`None` si la base responde; el motivo si no."""
    try:
        engine = create_engine(URL)
        with engine.connect() as con:
            con.execute(text("SELECT 1"))
        engine.dispose()
        return None
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def test_en_CI_la_base_TIENE_que_responder() -> None:
    """Sin esto, un servicio de Postgres caido da un job verde sobre nada."""
    motivo = _error_de_conexion()

    if motivo is None:
        return

    if not EN_CI:
        pytest.skip(f"Sin base de datos disponible (fuera de CI): {motivo}")

    pytest.fail(
        "La base no responde y estamos en CI. Las 34 pruebas que dependen de "
        "ella se habrian saltado en silencio y el job habria quedado verde "
        "sobre cero cobertura de aislamiento, claves foraneas y CHECK.\n"
        f"URL: {URL}\nMotivo: {motivo}"
    )


def test_en_CI_el_esquema_esta_cargado() -> None:
    """Responder no es lo mismo que estar lista.

    Una base recien creada y **vacia** acepta conexiones perfectamente. Las
    pruebas que buscan una planta o un rol del seed se saltarian una por una
    con "el seed no dejo ...", que se lee como un detalle y es la misma falla:
    el bucle de migraciones de CI no corrio.
    """
    if _error_de_conexion() is not None:
        if EN_CI:
            pytest.fail("La base no responde en CI; ver la prueba anterior.")
        pytest.skip("Sin base de datos disponible (fuera de CI)")

    engine = create_engine(URL)
    with engine.connect() as con:
        tablas = con.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalar_one()
    engine.dispose()

    if tablas > 0:
        return

    mensaje = (
        "La base responde pero no tiene ni una tabla: el bucle de migraciones "
        "no corrio. Las pruebas se saltarian con 'el seed no dejo ...', que se "
        "lee como un detalle del seed y es un esquema ausente."
    )
    if EN_CI:
        pytest.fail(mensaje)
    pytest.skip(mensaje)
