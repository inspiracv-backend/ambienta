"""El proceso de un aspecto se puede cambiar (#28, matriz por proceso).

`POST /iso14001/aspects` aceptaba `process_id` y `PATCH` no: el campo no estaba
en `EnvironmentalAspectUpdate`, y un campo que el schema no declara **se
descarta en silencio con 200**. Un aspecto quedaba para siempre en el proceso
con el que nacio, y la matriz filtrada por proceso no podia corregirse desde la
pantalla.

Y como el id llega del cuerpo, tiene que pasar por la misma comprobacion que en
el alta: las claves foraneas no pasan por RLS.
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
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"


def _proceso_de(empresa: str) -> str:
    with SessionLocal() as db:
        declarar(db, uuid.UUID(empresa))
        pid = db.execute(
            text("SELECT id FROM processes WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
        ).scalar()
    if pid is None:  # pragma: no cover
        pytest.skip(f"la empresa {empresa} no tiene procesos en el seed")
    return str(pid)


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
def aspecto(cliente):
    """Un aspecto `[QA]` sin proceso, creado y borrado aca."""
    planta = cliente.get("/api/v1/facilities/").json()
    if not planta:  # pragma: no cover
        pytest.skip("El seed no dejo plantas")
    r = cliente.post(
        "/api/v1/iso14001/aspects",
        json={
            "facility_id": planta[0]["id"],
            "activity": f"[QA] Proceso {uuid.uuid4().hex[:6]}",
            "aspect": "Consumo de agua",
            "impact_type": "agotamiento_de_recursos",
            "operating_condition": "normal",
        },
    )
    assert r.status_code == 201, r.text
    creado = r.json()
    try:
        yield creado
    finally:
        with SessionLocal() as db:
            declarar(db, uuid.UUID(EMPRESA_A))
            db.execute(text("DELETE FROM environmental_aspects WHERE id = :a"), {"a": creado["id"]})
            db.commit()


def test_se_le_asigna_un_proceso_y_queda_guardado(cliente, aspecto) -> None:
    proceso = _proceso_de(EMPRESA_A)

    r = cliente.patch(f"/api/v1/iso14001/aspects/{aspecto['id']}", json={"process_id": proceso})

    assert r.status_code == 200, r.text
    assert r.json()["process_id"] == proceso
    # La otra mitad: responder bien y no escribir seria el mismo engano.
    assert cliente.get(f"/api/v1/iso14001/aspects/{aspecto['id']}").json()["process_id"] == proceso


def test_con_null_queda_sin_proceso(cliente, aspecto) -> None:
    cliente.patch(f"/api/v1/iso14001/aspects/{aspecto['id']}", json={"process_id": _proceso_de(EMPRESA_A)})

    r = cliente.patch(f"/api/v1/iso14001/aspects/{aspecto['id']}", json={"process_id": None})

    assert r.status_code == 200, r.text
    assert r.json()["process_id"] is None


def test_no_se_cuelga_de_un_proceso_de_otra_empresa(cliente, aspecto) -> None:
    ajeno = _proceso_de(EMPRESA_B)

    r = cliente.patch(f"/api/v1/iso14001/aspects/{aspecto['id']}", json={"process_id": ajeno})

    assert r.status_code == 422, r.text
    assert cliente.get(f"/api/v1/iso14001/aspects/{aspecto['id']}").json()["process_id"] is None


def test_la_negativa_no_distingue_ajeno_de_inexistente(cliente, aspecto) -> None:
    ajeno = cliente.patch(
        f"/api/v1/iso14001/aspects/{aspecto['id']}", json={"process_id": _proceso_de(EMPRESA_B)}
    )
    inventado = cliente.patch(
        f"/api/v1/iso14001/aspects/{aspecto['id']}", json={"process_id": str(uuid.uuid4())}
    )

    assert ajeno.status_code == inventado.status_code == 422
    assert ajeno.json() == inventado.json()
