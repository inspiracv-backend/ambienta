"""Una empresa suspendida o cerrada queda en solo lectura (spec de RBAC, 21-sep).

Hasta el 21-sep `tenants.status` era una marca que la pantalla mostraba y **el
servidor no miraba en ningun lado** salvo el acceso de invitados: una empresa
suspendida seguia creando obligaciones y recibiendo avisos por correo.

Las pruebas escriben el estado de verdad en la base y lo **restauran en el
`finally`**: dejar una empresa del seed suspendida romperia el resto de la
suite de formas que no se parecen en nada a la causa. Los cuerpos que se mandan
son invalidos a proposito: con la guarda da 403, sin ella 422, y en ningun caso
se escribe nada.
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.deps import CODIGO_EMPRESA_SOLO_LECTURA  # noqa: E402
from app.main import app  # noqa: E402

CLIENTE = "a0000000-0000-0000-0000-000000000001"  # Minera Andes
GESTOR = "a0000000-0000-0000-0000-000000000002"  # EcoGestion, con contrato con Minera Andes


@contextmanager
def en_estado(tenant: str, estado: str):
    with SessionLocal() as db:
        previo = db.execute(text("SELECT status FROM tenants WHERE id = :t"), {"t": tenant}).scalar()
        db.execute(text("UPDATE tenants SET status = :e WHERE id = :t"), {"e": estado, "t": tenant})
        db.commit()
    try:
        yield
    finally:
        with SessionLocal() as db:
            db.execute(text("UPDATE tenants SET status = :e WHERE id = :t"), {"e": previo, "t": tenant})
            db.commit()


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
        yield c


def _escribir(c, tenant: str, cliente_de: str | None = None):
    """Un alta con cuerpo invalido: 403 si la guarda corta, 422 si no."""
    cabeceras = {"X-Tenant-Id": tenant}
    if cliente_de:
        cabeceras["X-Cliente-Id"] = cliente_de
    return c.post("/api/v1/obligations/", json={}, headers=cabeceras)


def _codigo(r) -> str | None:
    detalle = r.json().get("detail")
    return detalle.get("codigo") if isinstance(detalle, dict) else None


def test_una_empresa_activa_escribe(cliente) -> None:
    """La linea base: sin esto, una guarda que niega todo pasaria las demas."""
    r = _escribir(cliente, CLIENTE)

    assert r.status_code == 422, r.text


def test_suspendida_no_escribe(cliente) -> None:
    with en_estado(CLIENTE, "suspended"):
        r = _escribir(cliente, CLIENTE)

    assert r.status_code == 403, r.text
    assert _codigo(r) == CODIGO_EMPRESA_SOLO_LECTURA
    assert r.json()["detail"]["estado"] == "suspended"


def test_cerrada_tampoco(cliente) -> None:
    with en_estado(CLIENTE, "closed"):
        r = _escribir(cliente, CLIENTE)

    assert r.status_code == 403, r.text
    assert _codigo(r) == CODIGO_EMPRESA_SOLO_LECTURA


def test_suspendida_tampoco_comenta(cliente) -> None:
    """Comentar es escribir, aunque `comentarios` decida el permiso en el handler."""
    with en_estado(CLIENTE, "suspended"):
        r = cliente.post("/api/v1/comentarios/", json={}, headers={"X-Tenant-Id": CLIENTE})

    assert r.status_code == 403, r.text
    assert _codigo(r) == CODIGO_EMPRESA_SOLO_LECTURA


def test_suspendida_no_escribe_en_iso_ni_en_el_crm(cliente) -> None:
    """Los dos routers que se montaban sin la guarda: la suspension no los alcanzaba."""
    with en_estado(CLIENTE, "suspended"):
        iso = cliente.post("/api/v1/iso14001/aspects", json={}, headers={"X-Tenant-Id": CLIENTE})
        crm = cliente.post("/api/v1/crm/companies", json={}, headers={"X-Tenant-Id": CLIENTE})

    assert iso.status_code == 403 and _codigo(iso) == CODIGO_EMPRESA_SOLO_LECTURA, iso.text
    assert crm.status_code == 403 and _codigo(crm) == CODIGO_EMPRESA_SOLO_LECTURA, crm.text


def test_suspendida_sigue_leyendo(cliente) -> None:
    """Suspender no es quitarle los datos: tiene que poder sacar lo suyo."""
    with en_estado(CLIENTE, "suspended"):
        r = cliente.get("/api/v1/obligations/?limit=1", headers={"X-Tenant-Id": CLIENTE})

    assert r.status_code == 200, r.text


def test_el_gestor_no_escribe_por_un_cliente_suspendido(cliente) -> None:
    with en_estado(CLIENTE, "suspended"):
        r = _escribir(cliente, GESTOR, cliente_de=CLIENTE)

    assert r.status_code == 403, r.text
    assert _codigo(r) == CODIGO_EMPRESA_SOLO_LECTURA


def test_un_gestor_suspendido_no_escribe_por_un_cliente_activo(cliente) -> None:
    """La otra direccion: mirar solo la empresa efectiva lo dejaria pasar."""
    # La linea base del caso: con el gestor activo, el alta llega a validarse.
    assert _escribir(cliente, GESTOR, cliente_de=CLIENTE).status_code == 422
    with en_estado(GESTOR, "suspended"):
        r = _escribir(cliente, GESTOR, cliente_de=CLIENTE)

    assert r.status_code == 403, r.text
    assert _codigo(r) == CODIGO_EMPRESA_SOLO_LECTURA


def test_escribir_sobre_una_suspendida_desde_otra_activa_no_lo_corta_esta_guarda(cliente) -> None:
    """Es el camino del Admin Global para reactivarla: escribe desde la
    plataforma, que no esta suspendida. Otras guardas deciden si puede; esta no
    tiene que ser la que lo impida."""
    with en_estado(GESTOR, "suspended"):
        r = cliente.patch(
            f"/api/v1/tenants/{GESTOR}",
            json={"status": "no-es-un-estado"},
            headers={"X-Tenant-Id": CLIENTE},
        )

    assert _codigo(r) != CODIGO_EMPRESA_SOLO_LECTURA, r.text


def test_el_cron_pausa_los_avisos_de_una_suspendida() -> None:
    from app.tareas.avisos import _empresas

    with SessionLocal() as db:
        antes, en_pausa_antes = _empresas(db)
    assert uuid.UUID(GESTOR) in antes

    with en_estado(GESTOR, "suspended"):
        with SessionLocal() as db:
            ahora, en_pausa = _empresas(db)

    assert uuid.UUID(GESTOR) not in ahora
    assert en_pausa == en_pausa_antes + 1
