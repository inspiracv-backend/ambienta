"""Las claves foraneas editables no pueden apuntar fuera de la empresa.

Es el hueco que abre exponer PATCH sobre tablas con FK: **las restricciones de
Postgres no pasan por Row Level Security**. `fk_departments_facility` solo
exige que exista una fila en `facilities` con ese id; no mira el tenant. Asi
que un PATCH con la planta de otra empresa pasa la restriccion y deja la fila
apuntando fuera.

Peor que la fila incoherente es el oraculo: quien prueba identificadores
distingue "no existe" de "existe pero es de otro", y con eso enumera
identificadores ajenos sin verlos.

Se prueba contra Postgres real porque lo que se comprueba es precisamente que
la lectura del destino pase por RLS. Con un doble en memoria no habria RLS que
probar.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.crud.organization import crud_department, crud_facility
from app.routers._comun import validar_sin_ciclo, validar_visible

TENANT_1 = "a0000000-0000-0000-0000-000000000001"
TENANT_2 = "a0000000-0000-0000-0000-000000000002"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_1}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _id_de_otra_empresa(db: Session) -> uuid.UUID | None:
    """Una instalacion real del tenant 2, invisible desde el tenant 1."""
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_2}
    )
    ajena = db.execute(text("SELECT id FROM facilities LIMIT 1")).scalar()
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_1}
    )
    return ajena


def test_una_referencia_de_la_propia_empresa_se_acepta(db: Session) -> None:
    propia = crud_facility.get_multi(db, limit=1)[0]
    validar_visible(crud_facility, db, propia.id, campo="facility_id")


def test_una_referencia_de_otra_empresa_se_rechaza(db: Session) -> None:
    """El caso que las FK de Postgres dejan pasar."""
    ajena = _id_de_otra_empresa(db)
    if ajena is None:
        pytest.skip("La base de ejemplo no tiene instalaciones en el segundo tenant")

    with pytest.raises(HTTPException) as exc:
        validar_visible(crud_facility, db, ajena, campo="facility_id")
    assert exc.value.status_code == 422


def test_una_referencia_inexistente_se_rechaza_igual(db: Session) -> None:
    """Mismo 422 que la ajena, y es deliberado.

    Distinguirlas le diria a quien prueba identificadores cuales son reales en
    otra empresa. Desde afuera, "no existe" y "no es tuyo" son lo mismo.
    """
    with pytest.raises(HTTPException) as exc:
        validar_visible(crud_facility, db, uuid.uuid4(), campo="facility_id")
    assert exc.value.status_code == 422


def test_none_significa_sin_asignar_y_no_se_comprueba(db: Session) -> None:
    validar_visible(crud_facility, db, None, campo="facility_id")


def test_un_registro_no_puede_ser_su_propio_padre(db: Session) -> None:
    propio = uuid.uuid4()
    with pytest.raises(HTTPException) as exc:
        validar_sin_ciclo(
            crud_department,
            db,
            id_propio=propio,
            id_padre=propio,
            campo="parent_department_id",
        )
    assert exc.value.status_code == 422
    assert "propio padre" in exc.value.detail


def test_un_padre_valido_pasa(db: Session) -> None:
    existentes = crud_department.get_multi(db, limit=1)
    if not existentes:
        pytest.skip("La base de ejemplo no tiene departamentos")
    validar_sin_ciclo(
        crud_department,
        db,
        id_propio=uuid.uuid4(),
        id_padre=existentes[0].id,
        campo="parent_department_id",
    )


def _departamento_de_otra_empresa(db: Session) -> uuid.UUID | None:
    """Un departamento real del tenant 2, invisible desde el tenant 1."""
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_2}
    )
    ajeno = db.execute(text("SELECT id FROM departments LIMIT 1")).scalar()
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_1}
    )
    return ajeno


class TestElDepartamentoDeUnUsuario:
    """`users.department_id` tenia el mismo agujero, y estaba abierto.

    **El mismo campo, validado en `processes.py` y sin validar en `users.py`.**
    Es el modo de fallo que este repo ya conoce: la regla existe, se aplica en
    un lugar y se olvida en otro, y nada lo detecta porque el olvido no rompe
    nada visible — deja a una persona colgando de la estructura de otra empresa.
    """

    def test_asignar_un_departamento_ajeno_se_rechaza(self, db: Session) -> None:
        ajeno = _departamento_de_otra_empresa(db)
        if ajeno is None:  # pragma: no cover - seed sin departamentos en el 2
            pytest.skip("El seed no tiene departamentos en la segunda empresa.")

        with pytest.raises(HTTPException) as exc:
            validar_visible(crud_department, db, ajeno, campo="department_id")

        assert exc.value.status_code == 422

    def test_uno_inventado_da_el_mismo_error_que_uno_ajeno(self, db: Session) -> None:
        """**Los dos casos responden igual, a proposito.**

        Distinguirlos convertiria el campo en un oraculo: quien prueba
        identificadores al azar sabria cuales existen en otras empresas sin
        verlos nunca.
        """
        ajeno = _departamento_de_otra_empresa(db)
        if ajeno is None:  # pragma: no cover
            pytest.skip("El seed no tiene departamentos en la segunda empresa.")

        with pytest.raises(HTTPException) as por_ajeno:
            validar_visible(crud_department, db, ajeno, campo="department_id")
        with pytest.raises(HTTPException) as por_inexistente:
            validar_visible(crud_department, db, uuid.uuid4(), campo="department_id")

        assert por_ajeno.value.status_code == por_inexistente.value.status_code
        assert por_ajeno.value.detail == por_inexistente.value.detail


class TestElEndpointDeUsuariosLoAplica:
    """**Que la funcion valide no basta: hay que llamarla.**

    Las pruebas de arriba comprueban `validar_visible` en aislamiento, y pasaban
    en verde **con la guarda quitada del router**. Es el error de siempre: se
    prueba la pieza y no el camino. Esto va por HTTP.
    """

    @pytest.fixture
    def cliente(self, monkeypatch):
        from fastapi.testclient import TestClient

        from app.config import get_settings
        from app.db import SessionLocal
        from app.main import app

        monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)
        original = SessionLocal.kw.get("bind")
        motor = create_engine(URL)
        SessionLocal.configure(bind=motor)
        try:
            yield TestClient(app)
        finally:
            SessionLocal.configure(bind=original)
            motor.dispose()

    def test_patch_con_departamento_de_otra_empresa_da_422(
        self, cliente, db: Session
    ) -> None:
        ajeno = _departamento_de_otra_empresa(db)
        if ajeno is None:  # pragma: no cover
            pytest.skip("El seed no tiene departamentos en la segunda empresa.")

        propio = db.execute(
            text("SELECT id FROM users WHERE tenant_id = :t LIMIT 1"), {"t": TENANT_1}
        ).scalar()
        if propio is None:  # pragma: no cover
            pytest.skip("El seed no tiene usuarios en la primera empresa.")

        r = cliente.patch(
            f"/api/v1/users/{propio}",
            headers={"X-Tenant-Id": TENANT_1},
            json={"department_id": str(ajeno)},
        )

        assert r.status_code == 422, (
            f"Acepto un departamento de otra empresa: {r.status_code} {r.text}"
        )

    def test_patch_con_su_propio_departamento_sigue_funcionando(
        self, cliente, db: Session
    ) -> None:
        """La guarda no puede romper el caso legitimo, que es el 99 %."""
        propio_dep = db.execute(
            text("SELECT id FROM departments WHERE tenant_id = :t LIMIT 1"),
            {"t": TENANT_1},
        ).scalar()
        propio_usr = db.execute(
            text("SELECT id FROM users WHERE tenant_id = :t LIMIT 1"), {"t": TENANT_1}
        ).scalar()
        if propio_dep is None or propio_usr is None:  # pragma: no cover
            pytest.skip("El seed no alcanza para este caso.")

        r = cliente.patch(
            f"/api/v1/users/{propio_usr}",
            headers={"X-Tenant-Id": TENANT_1},
            json={"department_id": str(propio_dep)},
        )

        assert r.status_code == 200, r.text
