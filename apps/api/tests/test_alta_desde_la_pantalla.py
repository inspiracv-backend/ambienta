"""El alta de un registro de mejora con el cuerpo que arma la pantalla (#37).

`lib/audits-store.tsx::addNonConformity` manda esto, literal. Hasta el 13-sep
la pantalla pedia origen, producto y reclamo **y no mandaba ninguno**, asi que
una salida no conforme o un reclamo respondian 422 siempre, y el responsable era
un id de `mockUsers`. Si cambia uno de los dos lados, esto falla.
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


def _una_persona_y_una_planta() -> tuple[str, str]:
    with SessionLocal() as db:
        declarar(db, EMPRESA_A)
        persona = db.execute(text("SELECT id FROM users WHERE deleted_at IS NULL AND status = 'active' LIMIT 1")).scalar()
        planta = db.execute(text("SELECT id FROM facilities WHERE deleted_at IS NULL LIMIT 1")).scalar()
    if persona is None or planta is None:  # pragma: no cover
        pytest.skip("la empresa A no tiene persona o planta")
    return str(persona), str(planta)


def _borrar(nc_id: str) -> None:
    with SessionLocal() as db:
        declarar(db, EMPRESA_A)
        db.execute(text("DELETE FROM improvement_stage_entries WHERE nonconformity_id = :n"), {"n": nc_id})
        db.execute(text("DELETE FROM notifications WHERE context->>'nonconformity_id' = :n"), {"n": nc_id})
        db.execute(text("DELETE FROM nonconformities WHERE id = :n"), {"n": nc_id})
        db.commit()


def _cuerpo(**extra) -> dict:
    persona, planta = _una_persona_y_una_planta()
    return {
        "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
        "title": "[QA] Alta con el cuerpo de la pantalla",
        "description": "Derrame menor de aceite en bodega",
        "severity": "major",
        "facility_id": planta,
        "owner_user_id": persona,
        **extra,
    }


def test_una_salida_no_conforme_con_los_datos_del_formulario(cliente) -> None:
    r = cliente.post(
        BASE + "/",
        json=_cuerpo(
            record_type="salida_no_conforme",
            detection_origin="interna",
            product_data={"sku": "SKU-1", "lote": "L-9", "nombre": "Aceite", "cantidad": "3", "unidad": "L"},
        ),
    )
    assert r.status_code == 201, r.text
    nc = r.json()["id"]
    try:
        etapas = cliente.get(f"{BASE}/{nc}/etapas").json()
        assert len(etapas) == 5, "el registro nuevo tiene que nacer con su ciclo"
    finally:
        _borrar(nc)


def test_un_reclamo_con_los_datos_del_formulario(cliente) -> None:
    r = cliente.post(
        BASE + "/",
        json=_cuerpo(
            record_type="reclamo",
            detection_origin="externa",
            complaint_data={"cliente_nombre": "ACME", "canal": "Correo"},
        ),
    )
    assert r.status_code == 201, r.text
    _borrar(r.json()["id"])


def test_un_origen_de_auditoria_sin_pregunta_se_rechaza(cliente) -> None:
    """Por eso la pantalla solo ofrece esos origenes cuando viene de una auditoria."""
    r = cliente.post(BASE + "/", json=_cuerpo(record_type="no_conformidad", detection_origin="auditoria_interna"))
    assert r.status_code == 422, r.text
