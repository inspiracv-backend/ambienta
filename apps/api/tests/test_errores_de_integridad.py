"""El motivo de un rechazo de la base llega en un formato estable (escrituras-de-la-interfaz).

`detail` es para personas y se reescribe; `codigo` y `campos` son el contrato
sobre el que la interfaz puede ramificar. Hasta el 14-sep solo habia `detail`.
"""
from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.deps import declarar  # noqa: E402
from app.errores import campos_de  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"


class TestCamposDe:
    def test_un_not_null_usa_la_columna(self) -> None:
        assert campos_de(SimpleNamespace(column_name="title", constraint_name=None)) == ["title"]

    def test_sin_columna_ni_restriccion_da_lista_vacia_y_no_adivina(self) -> None:
        assert campos_de(SimpleNamespace(column_name=None, constraint_name=None)) == []
        assert campos_de(None) == []


@pytest.fixture(scope="module")
def cliente():
    import psycopg

    try:
        psycopg.connect(os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")).close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible ({exc}).")
    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:
        c.headers["X-Tenant-Id"] = EMPRESA_A
        yield c


def test_un_duplicado_real_responde_codigo_y_campo(cliente) -> None:
    codigo = f"qa_{uuid.uuid4().hex[:8]}"
    cuerpo = {"code": codigo, "name": "[QA] Duplicado", "shape": "texto_libre"}
    try:
        assert cliente.post("/api/v1/audits/catalogos/metodologias", json=cuerpo).status_code == 201
        r = cliente.post("/api/v1/audits/catalogos/metodologias", json=cuerpo)
        assert r.status_code == 409, r.text
        cuerpo_respuesta = r.json()
        assert cuerpo_respuesta["codigo"] == "valor_duplicado"
        assert cuerpo_respuesta["campos"] == ["code"]
        assert codigo not in r.text, "la respuesta no debe devolver valores de la fila"
    finally:
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            db.execute(text("DELETE FROM improvement_methodologies WHERE code = :c"), {"c": codigo})
            db.commit()


def test_las_columnas_salen_del_catalogo_y_sin_tenant(cliente) -> None:
    """Una clave foranea y un indice unico con `tenant_id`, sin datos de nadie."""
    assert campos_de(SimpleNamespace(column_name=None, constraint_name="uq_improvement_methodologies_code")) == ["code"]
    assert campos_de(SimpleNamespace(column_name=None, constraint_name="fk_departments_facility")) == ["facility_id"]
    assert campos_de(SimpleNamespace(column_name=None, constraint_name="no_existe_esta_restriccion")) == []
