"""Las relaciones entre normas se leen de la BCN (spec de la ingesta, 21-sep).

`legal_relations` existia desde el esquema inicial y nadie la escribia. Sin red:
`bcn.relaciones_de` se simula con lo que la BCN publica de verdad para el D.S.
609 y sus dos decretos modificatorios (consultado el 21-sep), y todo corre en
una transaccion que se deshace.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services import bcn
from app.tareas import sincronizar_bcn as tarea

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

DS_609, DS_3592, DS_601 = "121486", "176068", "230064"
AUSENTE = "999999999"  # una norma que el catalogo no tiene


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible: {exc}")
    s = Session(bind=conexion)
    if s.execute(
        text("SELECT count(*) FROM legal_norms WHERE external_norm_id IN (:a, :b) AND deleted_at IS NULL"),
        {"a": DS_609, "b": DS_3592},
    ).scalar() < 2:
        pytest.skip("Falta sincronizar el D.S. 609 y el 3592 (python -m app.tareas sincronizar-bcn)")
    # Se parte sin las relaciones de estas normas, aunque una sincronizacion real
    # ya las haya guardado: la prueba mide lo que escribe ella. Se deshace al final.
    s.execute(
        text(
            "DELETE FROM legal_relations WHERE source_norm_id IN (SELECT id FROM legal_norms WHERE external_norm_id = ANY(:c)) "
            "OR target_norm_id IN (SELECT id FROM legal_norms WHERE external_norm_id = ANY(:c))"
        ),
        {"c": [DS_609, DS_3592, DS_601]},
    )
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


def _id(db: Session, codigo: str):
    return db.execute(
        text("SELECT id FROM legal_norms WHERE external_norm_id = :c AND tenant_id IS NULL AND deleted_at IS NULL"),
        {"c": codigo},
    ).scalar_one()


def _codigo_de(uri: str) -> str | None:
    return {
        "/1998-07-20/609": DS_609,
        "/2000-09-26/3592": DS_3592,
        "/2004-09-08/601": DS_601,
    }.get(next((k for k in ("/1998-07-20/609", "/2000-09-26/3592", "/2004-09-08/601") if uri.endswith(k)), ""))


@pytest.fixture
def bcn_simulada(monkeypatch):
    """Lo que la BCN publica: el 3592 y el 601 modifican al 609, que lo declara
    desde su lado como `isModifiedBy`. Y una concordancia hacia una norma que no
    esta en el catalogo."""
    publica = {
        DS_609: [
            bcn.RelacionBCN("isModifiedBy", DS_3592),
            bcn.RelacionBCN("isModifiedBy", DS_601),
            bcn.RelacionBCN("agreeWith", AUSENTE),
        ],
        DS_3592: [bcn.RelacionBCN("modifiesTo", DS_609)],
        DS_601: [bcn.RelacionBCN("modifiesTo", DS_609)],
    }
    llamadas: list[str] = []

    def relaciones_de(uri):
        llamadas.append(uri)
        return publica.get(_codigo_de(uri) or "", [])

    monkeypatch.setattr(bcn, "relaciones_de", relaciones_de)
    return llamadas


def _relaciones(db: Session):
    return db.execute(
        text(
            "SELECT s.external_norm_id, t.external_norm_id, r.relation_type FROM legal_relations r "
            "JOIN legal_norms s ON s.id = r.source_norm_id JOIN legal_norms t ON t.id = r.target_norm_id "
            "WHERE :n IN (s.external_norm_id, t.external_norm_id) ORDER BY 1, 2"
        ),
        {"n": DS_609},
    ).all()


def test_la_modificacion_queda_una_vez_y_en_su_sentido(db, bcn_simulada) -> None:
    """El 609 dice "me modifica el 3592" y el 3592 dice "modifico al 609": es una
    sola relacion, del modificador al modificado."""
    informe = tarea.Informe()
    tarea.sincronizar_relaciones(db, informe)

    filas = [tuple(f) for f in _relaciones(db)]
    assert (DS_3592, DS_609, "modifica") in filas
    assert (DS_601, DS_609, "modifica") in filas
    assert (DS_609, DS_3592, "modifica") not in filas
    assert len([f for f in filas if f[2] == "modifica"]) == 2


def test_correr_dos_veces_no_duplica(db, bcn_simulada) -> None:
    tarea.sincronizar_relaciones(db, tarea.Informe())
    segunda = tarea.Informe()
    tarea.sincronizar_relaciones(db, segunda)

    assert segunda.relaciones_nuevas == 0
    assert len(_relaciones(db)) == 2


def test_hacia_una_norma_ausente_no_la_inventa_y_lo_anota(db, bcn_simulada) -> None:
    antes = db.execute(text("SELECT count(*) FROM legal_norms")).scalar()
    informe = tarea.Informe()
    tarea.sincronizar_relaciones(db, informe)

    assert db.execute(text("SELECT count(*) FROM legal_norms")).scalar() == antes
    assert {"norma": DS_609, "relacion": "agreeWith", "otra": AUSENTE} in informe.relaciones_sin_resolver


def test_un_fallo_de_la_fuente_en_una_norma_no_detiene_a_las_demas(db, monkeypatch) -> None:
    def relaciones_de(uri):
        if uri.endswith("/2000-09-26/3592"):
            raise TimeoutError("la BCN no respondio")
        if uri.endswith("/2004-09-08/601"):
            return [bcn.RelacionBCN("modifiesTo", DS_609)]
        return []

    monkeypatch.setattr(bcn, "relaciones_de", relaciones_de)
    informe = tarea.Informe()
    tarea.sincronizar_relaciones(db, informe)

    assert any(DS_3592 in e for e in informe.errores)
    assert (DS_601, DS_609, "modifica") in [tuple(f) for f in _relaciones(db)]
    assert tarea.estado_de(informe) == "partial"


def test_la_corrida_deja_en_la_bitacora_lo_que_no_se_resolvio(db, bcn_simulada, monkeypatch) -> None:
    monkeypatch.setattr(bcn, "buscar", lambda termino, limite=5: [])
    informe = tarea.sincronizar(db)
    meta = db.execute(
        text("SELECT response_metadata FROM norm_sync_runs ORDER BY id DESC LIMIT 1")
    ).scalar_one()

    assert meta["relaciones_nuevas"] == informe.relaciones_nuevas == 2
    assert {"norma": DS_609, "relacion": "agreeWith", "otra": AUSENTE} in meta["relaciones_sin_resolver"]


def test_se_consulta_desde_cualquiera_de_las_dos_normas(db, bcn_simulada) -> None:
    """El endpoint, con esta misma sesion: lo escrito no esta confirmado."""
    from app.deps import get_db
    from app.main import app

    tarea.sincronizar_relaciones(db, tarea.Informe())

    def sesion():
        yield db

    app.dependency_overrides[get_db] = sesion
    try:
        with TestClient(app) as c:
            c.headers["X-Tenant-Id"] = "a0000000-0000-0000-0000-000000000001"
            r609 = c.get(f"/api/v1/catalog/norms/{_id(db, DS_609)}/relations")
            r3592 = c.get(f"/api/v1/catalog/norms/{_id(db, DS_3592)}/relations")
            assert r609.status_code == r3592.status_code == 200, (r609.text, r3592.text)
            del_609, del_3592 = r609.json(), r3592.json()
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert {(r["norm_number"], r["relation_type"], r["sentido"]) for r in del_609} == {
        ("3592", "modifica", "entrante"),
        ("601", "modifica", "entrante"),
    }
    assert [(r["norm_number"], r["relation_type"], r["sentido"]) for r in del_3592] == [("609", "modifica", "saliente")]
