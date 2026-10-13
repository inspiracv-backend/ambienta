"""Quien emitio que documento queda en el registro (RNF-26, decision 9 del 21-sep).

Hasta el 21-sep la emision de un PDF se anotaba en el historial de la sesion
del navegador y se perdia al recargar. `POST /emisiones` la deja en
`audit_log`, con accion `download`.

**`audit_log` no se borra** (el rol de la aplicacion solo inserta y lee), asi
que estas pruebas dejan filas en la base de desarrollo. Llevan `[QA]` en el
titulo para reconocerlas.
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from datetime import date, timedelta

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.permisos_de_rutas import permiso_requerido  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"
AUDITORIA_A = "a0000030-0000-0000-0000-000000000001"  # AUD-2026-001, del seed


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


def _emitir(c, tenant: str, **cuerpo):
    datos = {"documento": "informe_de_auditoria", "titulo": f"[QA] Informe {uuid.uuid4().hex[:6]}", "formato": "pdf"}
    datos.update(cuerpo)
    return c.post("/api/v1/emisiones/", json=datos, headers={"X-Tenant-Id": tenant})


def test_pide_el_permiso_de_generar_reportes() -> None:
    assert permiso_requerido("/api/v1/emisiones/", "POST") == "report.generate"


def test_el_informe_queda_anotado_contra_su_auditoria(cliente) -> None:
    r = _emitir(cliente, EMPRESA_A, entidad_tipo="audits", entidad_id=AUDITORIA_A, filas=5)

    assert r.status_code == 201, r.text
    assert r.json()["action"] == "download"
    assert r.json()["entity_type"] == "audits" and r.json()["entity_id"] == AUDITORIA_A
    # Y aparece en el historial de esa auditoria, que es donde alguien lo busca.
    h = cliente.get(
        "/api/v1/historial/",
        params={"entity_type": "audit", "entity_id": AUDITORIA_A},
        headers={"X-Tenant-Id": EMPRESA_A},
    )
    assert h.status_code == 200, h.text
    emisiones = [e for e in h.json()["eventos"] if e["detalle"].get("accion") == "download"]
    assert emisiones, h.json()["eventos"][:3]
    assert emisiones[0]["resumen"] == "Documento emitido"


def test_lo_que_se_emitio_se_puede_leer_en_el_registro(cliente) -> None:
    titulo = f"[QA] Matriz {uuid.uuid4().hex[:6]}"
    r = _emitir(cliente, EMPRESA_A, documento="matriz_de_aspectos", titulo=titulo, formato="csv", filas=3, filtros=["Planta: Calama"])
    assert r.status_code == 201, r.text

    fila = next(
        f
        for f in cliente.get("/api/v1/system/audit-log?limit=20", headers={"X-Tenant-Id": EMPRESA_A}).json()
        if f["id"] == r.json()["id"]
    )
    assert fila["after_data"]["titulo"] == titulo
    assert fila["after_data"]["filtros"] == ["Planta: Calama"]
    assert fila["after_data"]["filas"] == 3


def test_contra_una_auditoria_ajena_responde_igual_que_si_no_existiera(cliente) -> None:
    ajena = _emitir(cliente, EMPRESA_B, entidad_tipo="audits", entidad_id=AUDITORIA_A)
    inventada = _emitir(cliente, EMPRESA_B, entidad_tipo="audits", entidad_id=str(uuid.uuid4()))

    assert ajena.status_code == inventada.status_code == 422
    assert ajena.json() == inventada.json()


def test_un_documento_fuera_de_la_lista_se_rechaza(cliente) -> None:
    assert _emitir(cliente, EMPRESA_A, documento="lo-que-sea").status_code == 422


def test_entidad_a_medias_se_rechaza(cliente) -> None:
    assert _emitir(cliente, EMPRESA_A, entidad_tipo="audits").status_code == 422


@contextmanager
def _suspendida(tenant: str):
    with SessionLocal() as db:
        previo = db.execute(text("SELECT status FROM tenants WHERE id = :t"), {"t": tenant}).scalar()
        db.execute(text("UPDATE tenants SET status = 'suspended' WHERE id = :t"), {"t": tenant})
        db.commit()
    try:
        yield
    finally:
        with SessionLocal() as db:
            db.execute(text("UPDATE tenants SET status = :e WHERE id = :t"), {"e": previo, "t": tenant})
            db.commit()


def test_una_empresa_suspendida_puede_exportar_y_queda_anotado(cliente) -> None:
    """Exportar esta permitido en solo lectura; perder su rastro no."""
    with _suspendida(EMPRESA_A):
        r = _emitir(cliente, EMPRESA_A, documento="reporte", formato="pdf")
        # La linea base del caso: cualquier otra escritura si se bloquea.
        otra = cliente.post("/api/v1/obligations/", json={}, headers={"X-Tenant-Id": EMPRESA_A})

    assert r.status_code == 201, r.text
    assert otra.status_code == 403


def test_el_registro_se_consulta_por_dias_de_la_empresa(cliente) -> None:
    r = _emitir(cliente, EMPRESA_A, documento="reporte", formato="csv")
    assert r.status_code == 201, r.text
    ident = r.json()["id"]
    hoy = date.today()
    cab = {"X-Tenant-Id": EMPRESA_A}

    # Un margen de un dia a cada lado: el huso de la empresa y el de la maquina
    # que corre la prueba pueden no coincidir, y la prueba no mide eso.
    dentro = cliente.get(
        f"/api/v1/system/audit-log?limit=50&desde={hoy - timedelta(days=1)}&hasta={hoy + timedelta(days=1)}", headers=cab
    ).json()
    antes = cliente.get(f"/api/v1/system/audit-log?limit=50&hasta={hoy - timedelta(days=2)}", headers=cab).json()

    assert ident in {f["id"] for f in dentro}
    assert ident not in {f["id"] for f in antes}


def test_cada_fila_trae_el_nombre_de_quien_actuo(cliente) -> None:
    filas = cliente.get("/api/v1/system/audit-log?limit=5", headers={"X-Tenant-Id": EMPRESA_A}).json()

    assert filas and all("actor_nombre" in f for f in filas)
