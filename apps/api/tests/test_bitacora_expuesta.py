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
    """Dentro de una transaccion que se deshace: la bitacora es de solo agregar
    (`db/33`), asi que una prueba ya no puede borrar lo que escribio. El endpoint
    lee con esta misma sesion."""
    from app.deps import get_db

    db = SessionLocal()
    try:
        fuente = db.execute(text("SELECT id FROM legal_sources WHERE code = 'BCN_LEYCHILE'")).scalar()
        if fuente is None:  # pragma: no cover
            pytest.skip("sin fuente BCN sembrada")
        db.execute(
            text(
                "INSERT INTO norm_sync_runs (source_id, started_at, finished_at, status, norms_created, response_metadata) VALUES "
                "(:f, now() + interval '1 hour', now() + interval '1 hour', 'success', 1, '{}'), "
                "(:f, now() + interval '2 hours', now() + interval '2 hours', 'partial', 0, '{\"sin_su_norma\": [\"ruidos (esperaba 38)\"]}')"
            ),
            {"f": fuente},
        )

        def sesion():
            yield db

        app.dependency_overrides[get_db] = sesion
        r = cliente.get("/api/v1/catalog/sync-runs", params={"limite": 2})
        assert r.status_code == 200, r.text
        corridas = r.json()
        assert [c["status"] for c in corridas] == ["partial", "success"]
        assert corridas[0]["response_metadata"]["sin_su_norma"] == ["ruidos (esperaba 38)"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.rollback()
        db.close()


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE norm_sync_runs SET status = 'success' WHERE id = (SELECT max(id) FROM norm_sync_runs)",
        "DELETE FROM norm_sync_runs WHERE id = (SELECT max(id) FROM norm_sync_runs)",
    ],
)
def test_la_aplicacion_no_puede_reescribir_la_bitacora(sentencia: str) -> None:
    """El spec: nadie edita la bitacora. Lo sostiene la base, no la ausencia de
    un endpoint: el rol `ambienta_app` solo inserta y lee (`db/33`)."""
    from sqlalchemy.exc import ProgrammingError

    with SessionLocal() as db:
        with pytest.raises(ProgrammingError, match="permission denied"):
            db.execute(text(sentencia))
        db.rollback()
