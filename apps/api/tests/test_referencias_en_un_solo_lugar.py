"""Toda escritura por `CRUDBase` rechaza claves foraneas hacia lo ajeno.

**Las FK de Postgres no pasan por RLS**: solo exigen que la fila exista. La regla
del repositorio era que cada endpoint que acepta un id en el cuerpo llame a
`validar_visible`, y se cumplia a medias —`routers/compliance.py` no lo llamaba
ni una vez hasta el 21-sep—. Desde ese dia la comprobacion vive en
`CRUDBase.create` y `update` (`_exigir_referencias`): el mismo punto unico que ya
tenian el borrado logico y el alcance.

Medido el 21-sep apagando la comprobacion central: `POST /obligations/` aceptaba
como responsable a una persona de otra empresa (201, y la fila quedaba escrita).
El aspecto ambiental, en cambio, ya lo rechazaba su router; queda como control de
que las dos barreras dan la misma respuesta.

Las pruebas directas corren en una transaccion que se deshace. Las de API solo
mandan cuerpos que se rechazan, asi que no escriben.
"""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.crud.organization import crud_department  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.organization import DepartmentCreate  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"


def _uno(sql: str, empresa: str):
    with SessionLocal() as db:
        db.execute(text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": empresa})
        valor = db.execute(text(sql)).scalar()
    if valor is None:
        pytest.skip(f"Falta el dato para la prueba: {sql}")
    return str(valor)


@pytest.fixture
def db():
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    sesion.execute(text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": EMPRESA_A})
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


@pytest.fixture(scope="module")
def cliente():
    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


PLANTA_B = "SELECT id FROM facilities WHERE deleted_at IS NULL ORDER BY id LIMIT 1"
PERSONA_B = "SELECT id FROM users WHERE deleted_at IS NULL ORDER BY id LIMIT 1"


class TestEnElCrud:
    def test_una_referencia_propia_se_acepta(self, db: Session) -> None:
        propia = db.execute(text("SELECT id FROM facilities WHERE deleted_at IS NULL LIMIT 1")).scalar()
        fila = crud_department.create(
            db, obj_in=DepartmentCreate(code="QA-REF", name="[QA] ref", facility_id=propia), tenant_id=EMPRESA_A
        )
        assert str(fila.facility_id) == str(propia)

    def test_una_ajena_se_rechaza_igual_que_una_inventada(self, db: Session) -> None:
        ajena = uuid.UUID(_uno(PLANTA_B, EMPRESA_B))
        respuestas = []
        for planta in (ajena, uuid.uuid4()):
            with pytest.raises(HTTPException) as e:
                crud_department.create(
                    db, obj_in=DepartmentCreate(code="QA-REF", name="[QA] ref", facility_id=planta), tenant_id=EMPRESA_A
                )
            respuestas.append((e.value.status_code, e.value.detail))
        assert respuestas[0] == respuestas[1] == (422, "facility_id no corresponde a un registro de esta empresa.")

    def test_tambien_al_editar(self, db: Session) -> None:
        from app.schemas.organization import DepartmentUpdate

        fila = db.execute(text("SELECT id FROM departments WHERE deleted_at IS NULL LIMIT 1")).scalar()
        if fila is None:
            pytest.skip("Sin departamentos en la empresa A")
        with pytest.raises(HTTPException) as e:
            crud_department.update(
                db,
                db_obj=crud_department.get(db, fila),
                obj_in=DepartmentUpdate(facility_id=uuid.UUID(_uno(PLANTA_B, EMPRESA_B))),
            )
        assert e.value.status_code == 422


def _dos(c, ruta: str, cuerpo: dict, campo: str, ajeno: str):
    ajena = c.post(ruta, json={**cuerpo, campo: ajeno}, headers={"X-Tenant-Id": EMPRESA_A})
    inventada = c.post(ruta, json={**cuerpo, campo: str(uuid.uuid4())}, headers={"X-Tenant-Id": EMPRESA_A})
    assert ajena.status_code == inventada.status_code == 422, (ajena.text, inventada.text)
    assert ajena.json() == inventada.json()


def test_un_aspecto_ambiental_en_la_planta_de_otra_empresa(cliente) -> None:
    """Ya lo validaba `routers/iso14001.py`: la respuesta no cambia."""
    cuerpo = {"activity": "[QA] ref", "aspect": "[QA] ref", "impact_type": "negativo"}
    _dos(cliente, "/api/v1/iso14001/aspects", cuerpo, "facility_id", _uno(PLANTA_B, EMPRESA_B))


def test_una_obligacion_a_cargo_de_alguien_de_otra_empresa(cliente) -> None:
    """Hueco real hasta el 21-sep: solo lo cierra la comprobacion central."""
    cuerpo = {"code": f"QA-REF-{uuid.uuid4().hex[:6]}", "title": "[QA] ref"}
    _dos(cliente, "/api/v1/obligations/", cuerpo, "owner_user_id", _uno(PERSONA_B, EMPRESA_B))
