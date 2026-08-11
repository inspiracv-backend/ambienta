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
