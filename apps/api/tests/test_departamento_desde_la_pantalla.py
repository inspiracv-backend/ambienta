"""El "departamento" de la pantalla crea un departamento organizativo y su proceso.

`lib/departamentos-store.tsx::addDepartamento` manda estos cuerpos, literales.
Hasta el 14-sep solo creaba el proceso: el perfil de empresa (RF-10) nunca se
completaba —el servidor exige una fila en `departments`— y a una persona interna
(RF-11) se le asignaba el id de un proceso como departamento, que la API rechaza.
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


def test_el_departamento_y_su_proceso_con_los_cuerpos_de_la_pantalla(cliente) -> None:
    sufijo = uuid.uuid4().hex[:6].upper()
    nombre = f"[QA] Chancado {sufijo}"
    ids: dict[str, str] = {}
    try:
        r = cliente.post("/api/v1/departments/", json={"code": f"DEP-QA{sufijo}", "name": nombre})
        assert r.status_code == 201, r.text
        ids["unidad"] = r.json()["id"]

        r = cliente.post(
            "/api/v1/processes/",
            json={
                "code": f"PROC-QA{sufijo}",
                "name": nombre,
                "process_type": "operational",
                "description": None,
                "responsible_user_id": None,
                "department_id": ids["unidad"],
            },
        )
        assert r.status_code == 201, r.text
        ids["proceso"] = r.json()["id"]
        assert r.json()["department_id"] == ids["unidad"]

        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            persona = db.execute(
                text("SELECT id FROM users WHERE deleted_at IS NULL AND user_type = 'internal' LIMIT 1")
            ).scalar()
            if persona is None:  # pragma: no cover
                pytest.skip("la empresa no tiene personas internas")
            anterior = db.execute(text("SELECT department_id FROM users WHERE id = :u"), {"u": persona}).scalar()
        ids["persona"], ids["anterior"] = str(persona), str(anterior) if anterior else ""

        # El defecto de fondo: el id de un PROCESO no es un departamento.
        r = cliente.patch(f"/api/v1/users/{persona}", json={"department_id": ids["proceso"]})
        assert r.status_code == 422, r.text
        # El departamento organizativo sí.
        r = cliente.patch(f"/api/v1/users/{persona}", json={"department_id": ids["unidad"]})
        assert r.status_code == 200, r.text
    finally:
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            if ids.get("persona") and ids.get("anterior"):
                db.execute(
                    text("UPDATE users SET department_id = :d WHERE id = :u"),
                    {"d": ids["anterior"], "u": ids["persona"]},
                )
            if ids.get("proceso"):
                db.execute(text("DELETE FROM processes WHERE id = :p"), {"p": ids["proceso"]})
            if ids.get("unidad"):
                db.execute(text("DELETE FROM departments WHERE id = :d"), {"d": ids["unidad"]})
            db.commit()
