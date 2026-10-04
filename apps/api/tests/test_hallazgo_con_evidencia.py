"""Un hallazgo de auditoria se sostiene en evidencia (ISO 19011, spec de mejoras).

`nonconformities` tenia `description` y nada mas: la evidencia, si alguien la
escribia, quedaba mezclada con el relato. Un hallazgo sin evidencia no se
sostiene cuando el auditado lo apela, que es cuando hace falta.

La regla vale para los registros con **origen en una auditoria**: un reclamo o
un riesgo de la revision anual nacen de otra cosa.
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

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
BASE = "/api/v1/audits/nonconformities"


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


@pytest.fixture
def item_de_auditoria() -> str:
    with SessionLocal() as db:
        declarar(db, uuid.UUID(EMPRESA_A))
        item = db.execute(
            text("SELECT id FROM audit_items WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
        ).scalar()
    if item is None:  # pragma: no cover
        pytest.skip("El seed no dejo items de auditoria")
    return str(item)


def _crear(cliente, **extra):
    cuerpo = {
        "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
        "title": "[QA] Hallazgo con evidencia",
        "description": "El procedimiento no se siguio.",
        "severity": "major",
    }
    cuerpo.update(extra)
    r = cliente.post(BASE + "/", json=cuerpo)
    if r.status_code == 201:
        with SessionLocal() as db:
            declarar(db, uuid.UUID(EMPRESA_A))
            db.execute(text("DELETE FROM nonconformities WHERE id = :n"), {"n": r.json()["id"]})
            db.commit()
    return r


def test_un_hallazgo_de_auditoria_sin_evidencia_se_rechaza(cliente, item_de_auditoria) -> None:
    r = _crear(
        cliente,
        detection_origin="auditoria_interna",
        audit_item_id=item_de_auditoria,
    )

    assert r.status_code == 422, r.text
    assert "evidencia objetiva" in r.text


def test_con_evidencia_se_acepta_y_queda_aparte_de_la_descripcion(cliente, item_de_auditoria) -> None:
    r = _crear(
        cliente,
        detection_origin="auditoria_interna",
        audit_item_id=item_de_auditoria,
        objective_evidence="Registro F-012 del 2 de octubre sin firma del operador.",
    )

    assert r.status_code == 201, r.text
    assert r.json()["objective_evidence"].startswith("Registro F-012")
    assert r.json()["description"] == "El procedimiento no se siguio."


def test_un_registro_que_no_sale_de_una_auditoria_no_la_exige(cliente) -> None:
    """Un riesgo que sale del analisis FODA nace de otra cosa."""
    r = _crear(cliente, detection_origin="analisis_foda")

    assert r.status_code == 201, r.text


def test_la_base_tambien_lo_exige(cliente, item_de_auditoria) -> None:
    """Lo mismo por SQL: la regla no vive solo en el esquema de la API."""
    from sqlalchemy.exc import IntegrityError

    with SessionLocal() as db:
        declarar(db, uuid.UUID(EMPRESA_A))
        with pytest.raises(IntegrityError, match="ck_nc_hallazgo_con_evidencia"):
            db.execute(
                text(
                    "INSERT INTO nonconformities (tenant_id, code, title, description, severity, "
                    "detection_origin, audit_item_id) "
                    "VALUES (:t, :c, '[QA] sin evidencia', 'x', 'major', 'auditoria_interna', :i)"
                ),
                {"t": EMPRESA_A, "c": f"PRB-{uuid.uuid4().hex[:6]}", "i": item_de_auditoria},
            )
        db.rollback()
