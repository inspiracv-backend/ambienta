"""La historia, los comentarios y los adjuntos respetan el alcance por planta.

Los tres se cuelgan de un registro con `comprobar_anclaje`, y hasta el 21-sep
esa comprobacion leia el registro con un `select` directo: **solo filtraba por
empresa** (RLS), no por planta. Alguien acotado a una planta podia, con solo
conocer el id de un registro de otra:

- leer su historia, con el antes y el despues de cada cambio;
- leer y escribir comentarios en el;
- adjuntarle documentos.

El spec de RBAC dice que un rol acotado no ve datos de otra planta y que
escribir fuera del alcance se rechaza. `CRUDBase._visibles()` ya lo aplicaba a
todo lo demas; esta era la puerta de al lado.

Las pruebas simulan Clerk —sin sesion identificada no hay alcance que aplicar—
y usan una persona `[QA]` propia, que se borra al terminar. Si la guarda
falla, el comentario que no debia quedar escrito se borra en la limpieza.
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
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.auth import CurrentUser  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.deps import declarar, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.obligations import Obligation  # noqa: E402
from app.models.organization import Department, Facility, Role, User, UserRole  # noqa: E402

EMPRESA = uuid.UUID("a0000000-0000-0000-0000-000000000001")


@pytest.fixture
def acotada():
    """Una encargada `[QA]` acotada a una planta, y una obligacion de otra planta
    y una de la empresa entera para mirar desde ahi."""
    import psycopg

    try:
        psycopg.connect(os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")).close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible ({exc}).")

    clerk_id = f"user_qa_{uuid.uuid4().hex[:10]}"
    with SessionLocal() as db:
        declarar(db, EMPRESA)
        ajena = db.scalars(
            select(Obligation).where(Obligation.facility_id.is_not(None), Obligation.deleted_at.is_(None))
        ).first()
        de_todos = db.scalars(
            select(Obligation).where(Obligation.facility_id.is_(None), Obligation.deleted_at.is_(None))
        ).first()
        if ajena is None or de_todos is None:  # pragma: no cover
            pytest.skip("el seed no tiene obligaciones con y sin planta")
        propia = db.scalar(
            select(Facility.id).where(Facility.id != ajena.facility_id, Facility.deleted_at.is_(None))
        )
        depto = db.scalar(select(Department.id).where(Department.deleted_at.is_(None)))
        rol = db.scalar(select(Role.id).where(Role.code == "encargado_ambiental"))
        if propia is None or depto is None or rol is None:  # pragma: no cover
            pytest.skip("al seed le falta otra planta, un departamento o el rol")
        persona = User(
            tenant_id=EMPRESA,
            department_id=depto,
            email=f"qa-{uuid.uuid4().hex[:10]}@prueba.cl",
            full_name="[QA] Acotada a una planta",
            user_type="internal",
            status="active",
            clerk_id=clerk_id,
        )
        db.add(persona)
        db.flush()
        db.add(UserRole(user_id=persona.id, role_id=rol, tenant_id=EMPRESA, facility_id=propia))
        db.flush()
        db.execute(
            text("UPDATE user_roles SET valid_from = now() - interval '1 day' WHERE user_id = :u"),
            {"u": str(persona.id)},
        )
        uid, id_ajena, id_de_todos = persona.id, ajena.id, de_todos.id
        db.commit()

    ajustes = get_settings()
    jwks_previo = ajustes.clerk_jwks_url
    ajustes.clerk_jwks_url = "https://prueba.clerk/jwks"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=clerk_id, tenant_id=str(EMPRESA)
    )
    try:
        with TestClient(app) as c:
            yield {"cliente": c, "ajena": id_ajena, "de_todos": id_de_todos}
    finally:
        # `dependency_overrides` es global: se limpia pase lo que pase.
        app.dependency_overrides.pop(get_current_user, None)
        ajustes.clerk_jwks_url = jwks_previo
        with SessionLocal() as db:
            declarar(db, EMPRESA)
            db.execute(text("DELETE FROM comments WHERE author_user_id = :u"), {"u": str(uid)})
            db.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": str(uid)})
            # **Si la guarda fallo, la persona ya no se puede borrar.** El
            # comentario que no debia escribirse quedo anotado en `audit_log`
            # con ella como autora, y ese registro no se borra ni se edita: la
            # clave foranea lo protege. Paso de verdad el 21-sep, en la prueba
            # de mutacion, y la limpieza entera se revertia dejando todo. Se
            # retira con borrado logico, que es lo que haria el sistema.
            punto = db.begin_nested()
            try:
                db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(uid)})
                punto.commit()
            except IntegrityError:
                punto.rollback()
                db.execute(
                    text(
                        "UPDATE users SET deleted_at = now(), status = 'disabled', "
                        "clerk_id = NULL WHERE id = :u"
                    ),
                    {"u": str(uid)},
                )
            db.commit()


def _historia(c, entity_id):
    return c.get("/api/v1/historial/", params={"entity_type": "obligation", "entity_id": str(entity_id)})


def test_no_lee_la_historia_de_un_registro_de_otra_planta(acotada) -> None:
    r = _historia(acotada["cliente"], acotada["ajena"])

    assert r.status_code == 422, r.text


def test_si_lee_la_de_un_registro_de_la_empresa_entera(acotada) -> None:
    """La otra mitad: una fila sin planta es de todos (regla 2 del alcance).
    Una guarda que niega todo tambien pasaria la prueba de arriba."""
    r = _historia(acotada["cliente"], acotada["de_todos"])

    assert r.status_code == 200, r.text


def test_la_negativa_no_distingue_ajeno_de_inexistente(acotada) -> None:
    """Mismo codigo y mismo mensaje: si no, el endpoint diria que ids existen."""
    ajena = _historia(acotada["cliente"], acotada["ajena"])
    inventada = _historia(acotada["cliente"], uuid.uuid4())

    assert ajena.status_code == inventada.status_code == 422
    assert ajena.json() == inventada.json()


def test_no_comenta_un_registro_de_otra_planta(acotada) -> None:
    r = acotada["cliente"].post(
        "/api/v1/comentarios/",
        json={
            "entity_type": "obligation",
            "entity_id": str(acotada["ajena"]),
            "body": "[QA] no deberia quedar escrito",
        },
    )

    assert r.status_code == 422, r.text
