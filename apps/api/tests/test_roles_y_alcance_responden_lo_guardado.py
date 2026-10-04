"""`PUT /users/{id}/roles` y `PUT /users/{id}/alcance` responden lo que guardaron.

Hasta el 21-sep armaban la respuesta **despues** de `db.commit()`. El commit se
lleva la empresa declarada, asi que la relectura veia cero filas:

| ruta | guardaba | respondia |
|---|---|---|
| `PUT /alcance` con una planta | la planta | `facility_ids: []` — **"sin acotar"** |
| `PUT /roles` con dos roles | los dos | `role_ids: []`, `codigos: []` |

El primero es el grave: en este sistema una lista vacia significa **toda la
empresa**, y la pantalla pinta a la persona con lo que responde la API. Un
administrador acotaba a alguien a una planta y veia en el acto que quedaba sin
acotar — lo contrario de lo que acababa de hacer.

No lo vio nadie por dos motivos que este repositorio ya conoce: las pruebas del
alcance van contra el **servicio**, con una sesion que no confirma, y las de
HTTP solo cubrian los rechazos. Tampoco lo vio el barrido de
`test_no_se_lee_despues_del_commit.py`, porque la consulta va dentro de una
funcion auxiliar; ahora tambien mira eso.

**Escribe de verdad en la base de desarrollo**, con una persona `[QA]` propia
que se borra al terminar: el `TestClient` confirma, y es justo lo que hace
falta para que el defecto aparezca.
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

from app.db import SessionLocal  # noqa: E402
from app.deps import declarar  # noqa: E402
from app.main import app  # noqa: E402
from app.models.organization import Department, Facility, Role, User, UserRole  # noqa: E402

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")


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
        c.headers["X-Tenant-Id"] = str(EMPRESA_A)
        yield c


def _rol(db, code: str) -> uuid.UUID:
    rid = db.scalar(select(Role.id).where(Role.tenant_id == EMPRESA_A, Role.code == code))
    if rid is None:  # pragma: no cover
        pytest.skip(f"La empresa no tiene el rol {code}")
    return rid


@pytest.fixture
def persona(cliente):
    """Una persona `[QA]` con un rol vigente desde ayer, confirmada y borrada aca."""
    with SessionLocal() as db:
        declarar(db, EMPRESA_A)
        depto = db.scalar(
            select(Department.id).where(Department.tenant_id == EMPRESA_A, Department.deleted_at.is_(None))
        )
        planta = db.scalar(
            select(Facility.id).where(Facility.tenant_id == EMPRESA_A, Facility.deleted_at.is_(None))
        )
        if depto is None or planta is None:  # pragma: no cover
            pytest.skip("El seed no dejo departamentos o plantas")
        fila = User(
            tenant_id=EMPRESA_A,
            department_id=depto,
            email=f"qa-{uuid.uuid4().hex[:10]}@prueba.cl",
            full_name="[QA] Persona de prueba",
            user_type="internal",
            status="active",
        )
        db.add(fila)
        db.flush()
        roles = {c: _rol(db, c) for c in ("encargado_ambiental", "operador")}
        db.add(UserRole(user_id=fila.id, role_id=roles["encargado_ambiental"], tenant_id=EMPRESA_A))
        db.flush()
        # Antedatado: con `valid_from = now()` el rol no seria vigente para una
        # consulta hecha en otra transaccion un instante antes.
        db.execute(
            text("UPDATE user_roles SET valid_from = now() - interval '1 day' WHERE user_id = :u"),
            {"u": str(fila.id)},
        )
        uid = fila.id
        db.commit()
    try:
        yield {"id": uid, "planta": planta, "roles": roles}
    finally:
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            db.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": str(uid)})
            db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(uid)})
            db.commit()


def test_acotar_responde_la_planta_y_no_sin_acotar(cliente, persona) -> None:
    r = cliente.put(
        f"/api/v1/users/{persona['id']}/alcance",
        json={"facility_id": str(persona["planta"])},
    )

    assert r.status_code == 200, r.text
    # `[]` aca seria "toda la empresa": lo contrario de lo que se guardo.
    assert r.json()["facility_ids"] == [str(persona["planta"])]


def test_lo_que_responde_acotar_es_lo_que_despues_se_lee(cliente, persona) -> None:
    """La otra mitad: que la respuesta coincida con la base, no solo que no este vacia."""
    escrito = cliente.put(
        f"/api/v1/users/{persona['id']}/alcance",
        json={"facility_id": str(persona["planta"])},
    ).json()

    leido = cliente.get(f"/api/v1/users/{persona['id']}/alcance").json()

    assert escrito["facility_ids"] == leido["facility_ids"] == [str(persona["planta"])]


def test_fijar_roles_responde_los_roles_que_quedaron(cliente, persona) -> None:
    ids = sorted(str(v) for v in persona["roles"].values())

    r = cliente.put(f"/api/v1/users/{persona['id']}/roles", json={"role_ids": ids})

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert sorted(cuerpo["role_ids"]) == ids
    assert cuerpo["codigos"] == ["encargado_ambiental", "operador"]


def test_lo_que_responde_fijar_roles_es_lo_que_despues_se_lee(cliente, persona) -> None:
    ids = [str(persona["roles"]["operador"])]

    escrito = cliente.put(f"/api/v1/users/{persona['id']}/roles", json={"role_ids": ids}).json()
    leido = cliente.get(f"/api/v1/users/{persona['id']}/roles").json()

    assert escrito["role_ids"] == ids
    assert escrito["codigos"] == ["operador"]
    assert leido["codigos"] == escrito["codigos"]
