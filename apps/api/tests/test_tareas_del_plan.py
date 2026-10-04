"""Tareas de un plan de accion (#169, cambio modelo-de-tareas-del-plan-de-accion).

Contra la base real y por HTTP: lo que se protege es un CHECK (`db/31`), RLS y
el orden de las rutas, y nada de eso se ve con una sesion simulada. Los datos se
siembran y se borran; lo sembrado lleva `[QA]`.
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
from sqlalchemy import create_engine, text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.deps import declarar  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"
PLANES = "/api/v1/audits/action-plans"


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


def _personas(empresa: str, n: int = 2) -> list[str]:
    with SessionLocal() as db:
        declarar(db, empresa)
        filas = db.execute(
            text("SELECT id FROM users WHERE deleted_at IS NULL AND status = 'active' ORDER BY email LIMIT :n"),
            {"n": n},
        ).scalars().all()
    if len(filas) < n:  # pragma: no cover
        pytest.skip(f"la empresa no tiene {n} personas activas")
    return [str(f) for f in filas]


def _borrar_plan(plan_id: str, empresa: str) -> None:
    with SessionLocal() as db:
        declarar(db, empresa)
        db.execute(text("DELETE FROM tasks WHERE action_plan_id = :p"), {"p": plan_id})
        db.execute(text("DELETE FROM action_plans WHERE id = :p"), {"p": plan_id})
        db.commit()


@pytest.fixture
def registro(cliente):
    """Un plan necesita origen (`ck_action_plans_origen`): se cuelga de un registro `[QA]`."""
    cliente.headers["X-Tenant-Id"] = EMPRESA_A
    r = cliente.post(
        "/api/v1/audits/nonconformities/",
        json={"code": f"PRB-{uuid.uuid4().hex[:8].upper()}", "title": "[QA] origen de planes",
              "description": "para #169", "severity": "major"},
    )
    assert r.status_code == 201, r.text
    nc = r.json()["id"]
    yield nc
    with SessionLocal() as db:
        declarar(db, EMPRESA_A)
        db.execute(text("DELETE FROM improvement_stage_entries WHERE nonconformity_id = :n"), {"n": nc})
        db.execute(text("DELETE FROM nonconformities WHERE id = :n"), {"n": nc})
        db.commit()


def _nuevo_plan(cliente, registro: str, titulo: str = "[QA] Plan con tareas") -> str:
    r = cliente.post(PLANES + "/", json={"title": titulo, "objective": "medir #169", "nonconformity_id": registro})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def plan(cliente, registro):
    pid = _nuevo_plan(cliente, registro)
    yield pid
    _borrar_plan(pid, EMPRESA_A)


def _tarea(cliente, plan_id: str, **extra) -> dict:
    r = cliente.post(f"{PLANES}/{plan_id}/tasks", json={"title": "[QA] tarea", **extra})
    assert r.status_code == 201, r.text
    return r.json()


class TestUnaTareaPerteneceAlPlan:
    def test_queda_en_la_base_leida_desde_otra_conexion(self, cliente, plan) -> None:
        t = _tarea(cliente, plan)
        engine = create_engine(os.environ["DATABASE_URL"])
        try:
            with engine.connect() as c:
                c.execute(text("SELECT set_config('ambienta.tenant_id', :t, false)"), {"t": EMPRESA_A})
                fila = c.execute(text("SELECT action_plan_id FROM tasks WHERE id = :i"), {"i": t["id"]}).scalar()
        finally:
            engine.dispose()
        assert str(fila) == plan

    def test_el_estado_sobrevive_y_completarla_fija_la_fecha(self, cliente, plan) -> None:
        t = _tarea(cliente, plan)
        r = cliente.patch(f"{PLANES}/tasks/{t['id']}", json={"status": "done"})
        assert r.status_code == 200, r.text
        releida = cliente.get(f"{PLANES}/tasks/{t['id']}").json()
        assert releida["status"] == "done"
        assert releida["completed_at"] is not None
        reabierta = cliente.patch(f"{PLANES}/tasks/{t['id']}", json={"status": "todo"}).json()
        assert reabierta["completed_at"] is None

    def test_se_listan_en_el_plan(self, cliente, plan) -> None:
        a = _tarea(cliente, plan, title="[QA] primera")
        b = _tarea(cliente, plan, title="[QA] segunda")
        ids = [t["id"] for t in cliente.get(f"{PLANES}/{plan}/tasks").json()]
        assert ids == [a["id"], b["id"]]


class TestUnSoloPadre:
    def test_con_obligacion_y_plan_se_rechaza_con_422(self, cliente, plan) -> None:
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            obligacion = db.execute(text("SELECT id FROM obligations WHERE deleted_at IS NULL LIMIT 1")).scalar()
        if obligacion is None:  # pragma: no cover
            pytest.skip("la empresa no tiene obligaciones")
        r = cliente.post(f"{PLANES}/{plan}/tasks", json={"title": "[QA] dos padres", "obligation_id": str(obligacion)})
        assert r.status_code == 422, r.text

    def test_la_base_tambien_lo_impide(self, plan) -> None:
        """El CHECK, no solo el servicio: un UPDATE a mano tiene que respetarlo."""
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            obligacion = db.execute(text("SELECT id FROM obligations WHERE deleted_at IS NULL LIMIT 1")).scalar()
            if obligacion is None:  # pragma: no cover
                pytest.skip("la empresa no tiene obligaciones")
            with pytest.raises(Exception, match="ck_tasks_un_solo_padre"):
                db.execute(
                    text(
                        "INSERT INTO tasks (tenant_id, title, obligation_id, action_plan_id) "
                        "VALUES (:t, '[QA] dos padres', :o, :p)"
                    ),
                    {"t": EMPRESA_A, "o": obligacion, "p": plan},
                )
            db.rollback()

    def test_sin_ningun_padre_se_acepta(self) -> None:
        """La otra mitad: la regla es "no dos", no "exactamente uno"."""
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            db.execute(text("INSERT INTO tasks (tenant_id, title) VALUES (:t, '[QA] suelta')"), {"t": EMPRESA_A})
            db.rollback()


class TestResponsables:
    def test_dos_tareas_del_mismo_plan_con_responsables_distintos(self, cliente, plan) -> None:
        uno, otro = _personas(EMPRESA_A)
        dueno_antes = cliente.get(f"{PLANES}/{plan}").json()["owner_user_id"]
        _tarea(cliente, plan, assignee_user_id=uno)
        _tarea(cliente, plan, assignee_user_id=otro)
        responsables = {t["assignee_user_id"] for t in cliente.get(f"{PLANES}/{plan}/tasks").json()}
        assert responsables == {uno, otro}
        assert cliente.get(f"{PLANES}/{plan}").json()["owner_user_id"] == dueno_antes, (
            "asignar tareas cambio el responsable del plan"
        )

    def test_lo_de_una_persona_entre_planes_y_sin_lo_de_otra(self, cliente, plan, registro) -> None:
        uno, otro = _personas(EMPRESA_A)
        segundo = _nuevo_plan(cliente, registro, "[QA] Segundo plan")
        try:
            a = _tarea(cliente, plan, assignee_user_id=uno)
            b = _tarea(cliente, segundo, assignee_user_id=uno)
            ajena = _tarea(cliente, plan, assignee_user_id=otro)
            r = cliente.get(f"{PLANES}/tasks/", params={"assignee_user_id": uno})
            assert r.status_code == 200, r.text
            ids = {t["id"] for t in r.json()}
            assert {a["id"], b["id"]} <= ids
            assert ajena["id"] not in ids
        finally:
            _borrar_plan(segundo, EMPRESA_A)

    def test_un_responsable_de_otra_empresa_se_rechaza(self, cliente, plan) -> None:
        (ajeno,) = _personas(EMPRESA_B, 1)
        r = cliente.post(f"{PLANES}/{plan}/tasks", json={"title": "[QA] ajena", "assignee_user_id": ajeno})
        assert r.status_code == 422, r.text


class TestAislamiento:
    def test_la_empresa_b_no_ve_las_tareas_del_plan_de_la_a(self, cliente, plan) -> None:
        t = _tarea(cliente, plan)
        try:
            cliente.headers["X-Tenant-Id"] = EMPRESA_B
            assert cliente.get(f"{PLANES}/{plan}/tasks").status_code == 404
            assert cliente.get(f"{PLANES}/tasks/{t['id']}").status_code == 404
        finally:
            cliente.headers["X-Tenant-Id"] = EMPRESA_A

    def test_la_empresa_b_no_crea_en_el_plan_de_la_a_y_responde_igual_que_uno_inventado(self, cliente, plan) -> None:
        try:
            cliente.headers["X-Tenant-Id"] = EMPRESA_B
            ajeno = cliente.post(f"{PLANES}/{plan}/tasks", json={"title": "[QA] intrusa"})
            inventado = cliente.post(f"{PLANES}/{uuid.uuid4()}/tasks", json={"title": "[QA] intrusa"})
        finally:
            cliente.headers["X-Tenant-Id"] = EMPRESA_A
        assert ajeno.status_code == inventado.status_code == 404
        assert ajeno.json() == inventado.json()
        assert cliente.get(f"{PLANES}/{plan}/tasks").json() == []


class TestRetirarElPlan:
    def test_las_tareas_sobreviven_al_retiro_del_plan(self, cliente, plan) -> None:
        t = _tarea(cliente, plan)
        assert cliente.delete(f"{PLANES}/{plan}").status_code == 204
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            viva = db.execute(
                text("SELECT deleted_at IS NULL FROM tasks WHERE id = :i"), {"i": t["id"]}
            ).scalar()
        assert viva is True


class TestLasRutasNoSeEnsombrecen:
    def test_la_consulta_por_persona_no_se_lee_como_un_plan(self, cliente) -> None:
        """Con `/action-plans/{plan_id}` declarada antes, "tasks" se leeria como UUID: 422."""
        r = cliente.get(f"{PLANES}/tasks/", params={"assignee_user_id": str(uuid.uuid4())})
        assert r.status_code == 200, r.text
        assert r.json() == []


class TestLasDeObligacionNoSeTocanDesdeElPlan:
    def test_una_tarea_de_obligacion_no_existe_para_las_rutas_del_plan(self, cliente) -> None:
        """Si no, el permiso de plan de accion editaria tareas de declaraciones."""
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            obligacion = db.execute(text("SELECT id FROM obligations WHERE deleted_at IS NULL LIMIT 1")).scalar()
            if obligacion is None:  # pragma: no cover
                pytest.skip("la empresa no tiene obligaciones")
            tid = db.execute(
                text("INSERT INTO tasks (tenant_id, title, obligation_id) VALUES (:t, '[QA] de obligacion', :o) RETURNING id"),
                {"t": EMPRESA_A, "o": obligacion},
            ).scalar()
            db.commit()
        try:
            assert cliente.get(f"{PLANES}/tasks/{tid}").status_code == 404
            assert cliente.patch(f"{PLANES}/tasks/{tid}", json={"status": "done"}).status_code == 404
        finally:
            with SessionLocal() as db:
                declarar(db, EMPRESA_A)
                db.execute(text("DELETE FROM tasks WHERE id = :i"), {"i": tid})
                db.commit()
