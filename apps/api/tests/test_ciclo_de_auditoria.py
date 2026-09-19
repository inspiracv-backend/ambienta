"""El ciclo de una auditoria desde la pantalla: crear, cargar el checklist, responder, cerrar.

La API existia y **ninguna pantalla la llamaba**: no se podia crear una
auditoria, ni cargarle preguntas, ni cerrarla. Estas pruebas mandan los cuerpos
literales de `apps/web/lib/ciclo-de-auditoria.ts`: si cambia uno de los dos
lados, fallan.

Y fijan dos guardas que faltaban:

- **El `PATCH` de la auditoria escribia `status` directo**, saltandose las
  transiciones que `/advance` si exige: `planned -> closed` pasaba, sin fecha de
  cierre.
- **El checklist se podia cambiar despues de cerrar.** El informe entregado y
  el sistema dirian cosas distintas.
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
def auditoria(cliente):
    """Una auditoria creada con el cuerpo de `crearAuditoria`, y borrada al final."""
    codigo = f"AUD-QA-{uuid.uuid4().hex[:6].upper()}"
    r = cliente.post(
        "/api/v1/audits/",
        json={
            "code": codigo,
            "title": "[QA] Auditoria interna de residuos",
            "audit_type": "internal",
            "scope": "Gestion de residuos peligrosos",
            "facility_id": None,
            "planned_start": "2026-09-22T15:00:00.000Z",
            "planned_end": "2026-09-23T15:00:00.000Z",
            "lead_auditor_user_id": None,
        },
    )
    assert r.status_code == 201, r.text
    creada = r.json()
    try:
        yield creada
    finally:
        with SessionLocal() as db:
            declarar(db, uuid.UUID(EMPRESA_A))
            db.execute(text("DELETE FROM audit_process_results WHERE audit_id = :a"), {"a": creada["id"]})
            db.execute(text("DELETE FROM audit_items WHERE audit_id = :a"), {"a": creada["id"]})
            db.execute(text("DELETE FROM audits WHERE id = :a"), {"a": creada["id"]})
            db.commit()


def _pregunta(cliente, auditoria, **extra):
    r = cliente.post(
        f"/api/v1/audits/{auditoria['id']}/items",
        json={"question": "¿Se registran los residuos peligrosos en SIDREP?", "process_id": None, **extra},
    )
    return r


def _avanzar(cliente, auditoria, estado):
    return cliente.post(f"/api/v1/audits/{auditoria['id']}/advance?new_status={estado}", json={})


def test_el_ciclo_completo_con_los_cuerpos_de_la_pantalla(cliente, auditoria) -> None:
    assert auditoria["status"] == "planned"

    r = _pregunta(cliente, auditoria)
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["result"] == "pending" and item["sequence"] >= 1

    assert _avanzar(cliente, auditoria, "active").json()["actual_start"] is not None

    r = cliente.patch(
        f"/api/v1/audits/{auditoria['id']}/items/{item['id']}",
        json={"result": "nonconform", "notes": "Dos manifiestos sin firma"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "nonconform"
    assert r.json()["assessed_at"] is not None

    assert _avanzar(cliente, auditoria, "reporting").status_code == 200
    r = _avanzar(cliente, auditoria, "closed")
    assert r.status_code == 200, r.text
    assert r.json()["actual_end"] is not None


def test_no_se_salta_estados(cliente, auditoria) -> None:
    r = _avanzar(cliente, auditoria, "closed")
    assert r.status_code == 400


def test_el_PATCH_no_es_una_puerta_trasera_para_el_estado(cliente, auditoria) -> None:
    r = cliente.patch(f"/api/v1/audits/{auditoria['id']}", json={"status": "closed"})
    assert r.status_code == 400, r.text
    assert cliente.get(f"/api/v1/audits/{auditoria['id']}").json()["status"] == "planned"


def test_el_PATCH_con_una_transicion_valida_si_la_aplica(cliente, auditoria) -> None:
    """La otra mitad: sin esto la guarda podria rechazar todo."""
    r = cliente.patch(f"/api/v1/audits/{auditoria['id']}", json={"status": "active", "title": "[QA] renombrada"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active" and r.json()["actual_start"] is not None
    assert r.json()["title"] == "[QA] renombrada"


@pytest.mark.parametrize("final", ["closed", "cancelled"])
def test_cerrada_su_checklist_ya_no_se_toca(cliente, auditoria, final) -> None:
    item = _pregunta(cliente, auditoria).json()
    if final == "closed":
        for estado in ("active", "reporting", "closed"):
            assert _avanzar(cliente, auditoria, estado).status_code == 200
    else:
        assert _avanzar(cliente, auditoria, "cancelled").status_code == 200

    base = f"/api/v1/audits/{auditoria['id']}/items"
    assert _pregunta(cliente, auditoria).status_code == 409
    assert cliente.patch(f"{base}/{item['id']}", json={"result": "conform"}).status_code == 409
    assert cliente.delete(f"{base}/{item['id']}").status_code == 409


def test_el_proceso_de_otra_empresa_no_entra_al_editar(cliente, auditoria) -> None:
    """El alta ya lo validaba; el `PATCH` no, y las claves foraneas no pasan por RLS."""
    with SessionLocal() as db:
        declarar(db, uuid.UUID(EMPRESA_B))
        ajeno = db.execute(
            text(
                "INSERT INTO processes (tenant_id, code, name, process_type) "
                "VALUES (:t, :c, '[QA] Proceso ajeno', 'operational') RETURNING id"
            ),
            {"t": EMPRESA_B, "c": f"PROC-QA{uuid.uuid4().hex[:6].upper()}"},
        ).scalar()
        db.commit()
    try:
        item = _pregunta(cliente, auditoria).json()

        r = cliente.patch(
            f"/api/v1/audits/{auditoria['id']}/items/{item['id']}", json={"process_id": str(ajeno)}
        )

        assert r.status_code == 422, r.text
    finally:
        with SessionLocal() as db:
            declarar(db, uuid.UUID(EMPRESA_B))
            db.execute(text("DELETE FROM processes WHERE id = :p"), {"p": ajeno})
            db.commit()


# ── Lo que una auditoria entregada ya no admite (revision del 19-sep) ──────


def test_no_se_cierra_sin_fecha_de_cierre_ni_se_antedata(cliente, auditoria) -> None:
    """Las marcas reales las pone el servidor: el cuerpo ya no las trae.

    Mandandolas se podia cerrar con `actual_end: null` —una auditoria cerrada sin
    fecha de cierre— o fecharla cuando conviniera. Es la fecha que mira un
    certificador para saber si el trabajo se hizo dentro del periodo.
    """
    for estado in ("active", "reporting"):
        assert _avanzar(cliente, auditoria, estado).status_code == 200

    r = cliente.patch(
        f"/api/v1/audits/{auditoria['id']}",
        json={"status": "closed", "actual_end": None, "actual_start": "2020-01-01T00:00:00Z"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["actual_end"] is not None, "se cerro sin fecha de cierre"
    assert not r.json()["actual_start"].startswith("2020"), "se antedato el inicio"


def test_una_auditoria_cerrada_no_se_edita(cliente, auditoria) -> None:
    for estado in ("active", "reporting", "closed"):
        assert _avanzar(cliente, auditoria, estado).status_code == 200

    r = cliente.patch(f"/api/v1/audits/{auditoria['id']}", json={"title": "[QA] otra cosa"})

    assert r.status_code == 409, r.text
    assert cliente.get(f"/api/v1/audits/{auditoria['id']}").json()["title"].endswith("residuos")


@pytest.mark.parametrize("campo", ["status", "title"])
def test_un_null_explicito_es_422_y_no_409(cliente, auditoria, campo: str) -> None:
    """Lo traduce el manejador de errores de integridad (`campo_obligatorio`).

    Se midio antes de escribir nada: la revision afirmaba que respondia 409, y
    responde 422. Queda fijado para que siga asi.
    """
    r = cliente.patch(f"/api/v1/audits/{auditoria['id']}", json={campo: None})

    assert r.status_code == 422, r.text


def test_los_veredictos_de_proceso_tambien_se_congelan(cliente, auditoria) -> None:
    """La matriz del informe entregado no cambia despues de cerrar.

    Congelar solo el checklist dejaba la otra mitad abierta: el veredicto por
    proceso es lo que el informe muestra por fila.
    """
    with SessionLocal() as db:
        declarar(db, uuid.UUID(EMPRESA_A))
        proceso = db.execute(
            text("SELECT id FROM processes WHERE deleted_at IS NULL LIMIT 1")
        ).scalar()
    if proceso is None:  # pragma: no cover
        pytest.skip("La empresa A no tiene procesos")

    base = f"/api/v1/audits/{auditoria['id']}/procesos"
    r = cliente.post(base, json={"process_id": str(proceso), "classification": "no_conforme"})
    assert r.status_code == 201, r.text
    veredicto = r.json()["id"]

    for estado in ("active", "reporting", "closed"):
        assert _avanzar(cliente, auditoria, estado).status_code == 200

    assert cliente.patch(f"{base}/{veredicto}", json={"classification": "conforme"}).status_code == 409
    assert cliente.delete(f"{base}/{veredicto}").status_code == 409
    assert cliente.post(base, json={"process_id": str(proceso), "classification": "conforme"}).status_code == 409
    assert cliente.get(f"{base}/{veredicto}").json()["classification"] == "no_conforme"
