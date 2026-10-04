"""Un gestor actua por su cliente con Clerk configurado (RF-64 a RF-66).

## Lo que se midio el 21-sep

`test_gestor_y_sus_clientes.py` prueba la puerta de `X-Cliente-Id` en modo
desarrollo, donde `exigir_permiso_de_la_ruta` no corre. Con Clerk si corre, y
buscaba a la persona y sus roles con la sesion declarada con la empresa **del
cliente**: RLS le escondia la fila del gestor, que es de otra empresa, y
respondia `permiso_insuficiente` en todo. El gestor leia lo suyo y **no podia
hacer nada por sus clientes**, que es para lo que existe.

Ahora la persona y sus permisos se leen en su propia empresa. Estas pruebas
simulan Clerk —como `test_admin_global_no_edita.py`— con personas `[QA]` de la
empresa gestora, que se borran al terminar. Las escrituras mandan cuerpos
invalidos: con permiso dan 422, sin permiso 403, y nunca se escribe nada.
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
from sqlalchemy import select, text  # noqa: E402

from app.auth import CurrentUser  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.deps import CODIGO_SIN_PERMISO, declarar, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.organization import Department, Role, User, UserRole  # noqa: E402

GESTOR = uuid.UUID("a0000000-0000-0000-0000-000000000002")  # EcoGestion
CLIENTE = "a0000000-0000-0000-0000-000000000001"  # Minera Andes, con contrato


@pytest.fixture
def como_gestor():
    """Arma un cliente HTTP como una persona `[QA]` del gestor, con ese rol."""
    import psycopg

    try:
        psycopg.connect(os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")).close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible ({exc}).")
    ajustes = get_settings()
    jwks_previo = ajustes.clerk_jwks_url
    creadas: list[uuid.UUID] = []
    clientes: list[TestClient] = []

    def armar(rol: str) -> TestClient:
        clerk_id = f"user_qa_{uuid.uuid4().hex[:10]}"
        with SessionLocal() as db:
            declarar(db, GESTOR)
            depto = db.scalar(select(Department.id).where(Department.deleted_at.is_(None)))
            role_id = db.scalar(select(Role.id).where(Role.code == rol))
            if depto is None or role_id is None:  # pragma: no cover
                pytest.skip("al seed del gestor le falta un departamento o el rol")
            persona = User(
                tenant_id=GESTOR,
                department_id=depto,
                email=f"qa-{uuid.uuid4().hex[:10]}@prueba.cl",
                full_name="[QA] Gestor con Clerk",
                user_type="internal",
                status="active",
                clerk_id=clerk_id,
            )
            db.add(persona)
            db.flush()
            db.add(UserRole(user_id=persona.id, role_id=role_id, tenant_id=GESTOR))
            db.flush()
            db.execute(
                text("UPDATE user_roles SET valid_from = now() - interval '1 day' WHERE user_id = :u"),
                {"u": str(persona.id)},
            )
            creadas.append(persona.id)
            db.commit()
        ajustes.clerk_jwks_url = "https://prueba.clerk/jwks"
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id=clerk_id, tenant_id=str(GESTOR)
        )
        c = TestClient(app)
        clientes.append(c)
        return c

    try:
        yield armar
    finally:
        # `dependency_overrides` es global: se limpia pase lo que pase.
        app.dependency_overrides.pop(get_current_user, None)
        ajustes.clerk_jwks_url = jwks_previo
        for c in clientes:
            c.close()
        with SessionLocal() as db:
            declarar(db, GESTOR)
            for uid in creadas:
                db.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": str(uid)})
                db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(uid)})
            db.commit()


def test_el_gestor_lee_lo_de_su_cliente(como_gestor) -> None:
    c = como_gestor("admin_empresa")

    r = c.get("/api/v1/obligations/?limit=5", headers={"X-Cliente-Id": CLIENTE})

    assert r.status_code == 200, r.text
    assert r.json() and {f["tenant_id"] for f in r.json()} == {CLIENTE}


def test_el_gestor_escribe_por_su_cliente_si_su_rol_lo_permite(como_gestor) -> None:
    c = como_gestor("admin_empresa")

    r = c.post("/api/v1/obligations/", json={}, headers={"X-Cliente-Id": CLIENTE})

    # 422 = paso la guarda y llego a validar el cuerpo.
    assert r.status_code == 422, r.text


def test_los_permisos_son_los_de_su_rol_en_su_empresa(como_gestor) -> None:
    """La otra mitad: arreglar la busqueda no puede dar permiso a cualquiera.
    El operador lee obligaciones y no las escribe, tambien por un cliente."""
    c = como_gestor("operador")

    lee = c.get("/api/v1/obligations/?limit=1", headers={"X-Cliente-Id": CLIENTE})
    escribe = c.post("/api/v1/obligations/", json={}, headers={"X-Cliente-Id": CLIENTE})

    assert lee.status_code == 200, lee.text
    assert escribe.status_code == 403, escribe.text
    assert escribe.json()["detail"]["codigo"] == CODIGO_SIN_PERMISO
    assert escribe.json()["detail"]["permiso"] == "obligation.write"
