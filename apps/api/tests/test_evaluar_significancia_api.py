"""Evaluar la significancia **por la API**, no por el servicio (#44, §6.1.2).

El servicio estaba probado y el endpoint respondia **500**: hacia `db.commit()`
y despues `db.refresh(aspecto)`, y el commit se lleva la empresa declarada, asi
que la recarga ve cero filas. Nadie lo noto porque **ninguna pantalla lo
llamaba**; se encontro el 20-sep, al conectarlo, probandolo en el navegador.

Es la leccion que este repositorio ya escribio dos veces: una suite que solo
prueba servicios no dice nada sobre si el endpoint funciona.
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


@pytest.fixture
def aspecto(cliente):
    """Un aspecto propio, creado y borrado aca: la evaluacion escribe de verdad."""
    planta = cliente.get("/api/v1/facilities/").json()
    if not planta:  # pragma: no cover
        pytest.skip("El seed no dejo plantas")
    r = cliente.post(
        "/api/v1/iso14001/aspects",
        json={
            "facility_id": planta[0]["id"],
            "activity": f"[QA] Evaluacion {uuid.uuid4().hex[:6]}",
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


def _evaluar(cliente, aspecto, frecuencia, severidad, legal):
    return cliente.post(
        f"/api/v1/iso14001/aspects/{aspecto['id']}/evaluate",
        json={"frequency_score": frecuencia, "severity_score": severidad, "legal_score": legal},
    )


def test_un_aspecto_nace_sin_evaluar(cliente, aspecto) -> None:
    """`pending` dice la verdad; `not_significant` seria el sistema afirmando
    que un aspecto no importa cuando lo que pasa es que nadie lo miro."""
    assert aspecto["significance"] == "pending"
    assert aspecto["total_score"] is None


def test_evaluar_responde_200_con_el_veredicto_y_sus_motivos(cliente, aspecto) -> None:
    r = _evaluar(cliente, aspecto, 8, 7, 3)

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["aspect"]["significance"] == "significant"
    assert cuerpo["aspect"]["total_score"] == 56
    assert any("umbral" in m for m in cuerpo["motivos"])


def test_queda_guardado_y_se_puede_volver_a_leer(cliente, aspecto) -> None:
    """La otra mitad: responder bien y no escribir seria el mismo enga単o."""
    _evaluar(cliente, aspecto, 8, 7, 3)

    leido = cliente.get(f"/api/v1/iso14001/aspects/{aspecto['id']}").json()

    assert leido["significance"] == "significant"
    assert leido["frequency_score"] == 8 and leido["severity_score"] == 7


def test_magnitud_baja_con_requisito_legal_igual_es_significativo(cliente, aspecto) -> None:
    """El caso raro y correcto: se gestiona por la obligacion legal, no por la
    magnitud. Leyendo solo `total_score` pareceria un error, y por eso la API
    devuelve **por que**."""
    r = _evaluar(cliente, aspecto, 2, 2, 9)

    cuerpo = r.json()
    assert cuerpo["aspect"]["significance"] == "significant"
    assert cuerpo["aspect"]["total_score"] == 4
    assert any("legal" in m for m in cuerpo["motivos"])


def test_un_puntaje_fuera_de_rango_se_rechaza(cliente, aspecto) -> None:
    assert _evaluar(cliente, aspecto, 0, 5, 5).status_code == 422
    assert cliente.get(f"/api/v1/iso14001/aspects/{aspecto['id']}").json()["significance"] == "pending"
