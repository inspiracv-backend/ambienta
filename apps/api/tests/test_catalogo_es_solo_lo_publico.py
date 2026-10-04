"""`GET /catalog/norms` lista **solo el catalogo publico**, no las normas propias.

## Lo que se midio el 21-sep

El router del catalogo se monta con `exigir_permiso_de_la_ruta`, que pide
`get_tenant_db`, asi que la sesion de `list_norms` —aunque pida `get_db`—
**viene con la empresa declarada** (lo advierte el docstring de `deps.get_db`).
Y el listado no filtraba `tenant_id`: devolvia lo publico **mas las normas
propias de quien pregunta**.

La Matriz Legal pide las dos listas —`/catalog/norms` y
`/compliance/normativa-propia/`— y las concatena, contando con que son
disjuntas. Con una sola RCA cargada, la norma aparecia **dos veces**. No se
veia porque el seed no tiene normas propias, y en modo desarrollo la web pedia
el catalogo sin empresa (y recibia 401).

La prueba crea una RCA `[QA]` propia y la borra al terminar.
"""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.deps import declarar  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA = "a0000000-0000-0000-0000-000000000001"


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
        c.headers["X-Tenant-Id"] = EMPRESA
        yield c


@pytest.fixture
def rca(cliente):
    titulo = f"[QA] RCA propia {uuid.uuid4().hex[:8]}"
    r = cliente.post(
        "/api/v1/compliance/normativa-propia/",
        json={"fuente": "RCA", "norm_type": "RCA", "title": titulo},
    )
    assert r.status_code == 201, r.text
    norma = r.json()
    try:
        yield norma
    finally:
        with SessionLocal() as db:
            declarar(db, uuid.UUID(EMPRESA))
            db.execute(text("DELETE FROM legal_articles WHERE norm_version_id IN (SELECT id FROM legal_norm_versions WHERE norm_id = :n)"), {"n": norma["id"]})
            db.execute(text("DELETE FROM legal_norm_versions WHERE norm_id = :n"), {"n": norma["id"]})
            db.execute(text("DELETE FROM legal_norms WHERE id = :n"), {"n": norma["id"]})
            db.commit()


def test_la_norma_propia_no_sale_en_el_catalogo(cliente, rca) -> None:
    r = cliente.get("/api/v1/catalog/norms", params={"buscar": rca["title"]})

    assert r.status_code == 200, r.text
    assert r.json() == [], "una norma propia salio en el catalogo publico: la matriz la mostraria dos veces"


def test_sigue_saliendo_en_la_normativa_propia(cliente, rca) -> None:
    """La otra mitad: sacarla del catalogo no puede hacerla desaparecer."""
    r = cliente.get("/api/v1/compliance/normativa-propia/")

    assert r.status_code == 200, r.text
    assert rca["id"] in {n["id"] for n in r.json()}


def test_el_catalogo_sigue_trayendo_lo_publico(cliente) -> None:
    r = cliente.get("/api/v1/catalog/norms?limit=5")

    assert r.status_code == 200, r.text
    assert r.json() and all(n.get("tenant_id") is None for n in r.json())
