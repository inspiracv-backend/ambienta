"""La bitacora de la BCN se expone (ingesta-normativa-bcn): "nadie escribe y nadie expone"."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"


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


def test_la_ultima_corrida_sale_primera_con_lo_que_no_encontro(cliente) -> None:
    with SessionLocal() as db:
        fuente = db.execute(text("SELECT id FROM legal_sources WHERE code = 'BCN_LEYCHILE'")).scalar()
        if fuente is None:  # pragma: no cover
            pytest.skip("sin fuente BCN sembrada")
        ids = db.execute(
            text(
                "INSERT INTO norm_sync_runs (source_id, started_at, finished_at, status, norms_created, response_metadata) VALUES "
                "(:f, now() + interval '1 hour', now() + interval '1 hour', 'success', 1, '{}'), "
                "(:f, now() + interval '2 hours', now() + interval '2 hours', 'partial', 0, '{\"sin_su_norma\": [\"ruidos (esperaba 38)\"]}') "
                "RETURNING id"
            ),
            {"f": fuente},
        ).scalars().all()
        db.commit()
    try:
        r = cliente.get("/api/v1/catalog/sync-runs", params={"limite": 2})
        assert r.status_code == 200, r.text
        corridas = r.json()
        assert [c["status"] for c in corridas] == ["partial", "success"]
        assert corridas[0]["response_metadata"]["sin_su_norma"] == ["ruidos (esperaba 38)"]
    finally:
        with SessionLocal() as db:
            db.execute(text("DELETE FROM norm_sync_runs WHERE id = ANY(:i)"), {"i": list(ids)})
            db.commit()
