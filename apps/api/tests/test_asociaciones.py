"""Las tablas de union se pueden quitar y volver a poner.

Es el caso que rompio al escribirlas, y no es un caso raro: en una tabla de
asociacion volver a agregar algo que se quito es **lo normal**. Una persona se
reincorpora a una auditoria, un proceso vuelve a una planta, un operador
recupera su certificacion.

La clave primaria de estas tablas es `(padre, hijo)` y **no es parcial sobre
`deleted_at`**, asi que una fila dada de baja sigue ocupando la clave. Insertar
de nuevo la misma pareja choca contra una fila que el usuario no puede ver, y
como la API no tiene manejador de `IntegrityError`, sale un 500.

Se prueba contra Postgres real porque lo que se comprueba es precisamente el
comportamiento de la restriccion de unicidad.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.organization import FacilityProcess
from app.routers._comun import CRUDAsociacion
from app.schemas.organization import FacilityProcessCreateAnidado

TENANT_1 = "a0000000-0000-0000-0000-000000000001"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

crud = CRUDAsociacion(FacilityProcess, "facility_id", "process_id")


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
        sesion.rollback()  # nada de lo que hagan estas pruebas se persiste
        sesion.close()
        conexion.close()
        engine.dispose()


@pytest.fixture
def par(db: Session):
    """Una pareja (planta, proceso) que ya existe en los datos de ejemplo."""
    fila = db.execute(
        text("SELECT facility_id, process_id FROM facility_processes LIMIT 1")
    ).first()
    if fila is None:
        pytest.skip("La base de ejemplo no tiene procesos por planta")
    return fila[0], fila[1]


def test_quitar_y_volver_a_poner_no_revienta(db: Session, par) -> None:
    """El caso que daba 500 por violacion de clave primaria."""
    padre, hijo = par

    assert crud.borrar(db, padre_id=padre, hijo_id=hijo) is not None
    assert crud.obtener(db, padre, hijo) is None

    reinstalada = crud.crear(
        db,
        padre_id=padre,
        hijo_id=hijo,
        datos=FacilityProcessCreateAnidado(is_primary=True),
        tenant_id=TENANT_1,
    )
    assert reinstalada is not None
    assert crud.obtener(db, padre, hijo) is not None


def test_al_reinstalar_mandan_los_datos_nuevos(db: Session, par) -> None:
    """Quien la vuelve a agregar declara las condiciones de ahora, no las de antes."""
    padre, hijo = par
    crud.actualizar(
        db,
        db_obj=crud.obtener(db, padre, hijo),
        datos=FacilityProcessCreateAnidado(is_primary=True, scope_notes="antes"),
    )
    crud.borrar(db, padre_id=padre, hijo_id=hijo)

    reinstalada = crud.crear(
        db,
        padre_id=padre,
        hijo_id=hijo,
        datos=FacilityProcessCreateAnidado(is_primary=False, scope_notes="ahora"),
        tenant_id=TENANT_1,
    )
    assert reinstalada.scope_notes == "ahora"
    assert reinstalada.is_primary is False


def test_no_se_duplica_la_fila_al_reinstalar(db: Session, par) -> None:
    padre, hijo = par
    crud.borrar(db, padre_id=padre, hijo_id=hijo)
    crud.crear(
        db,
        padre_id=padre,
        hijo_id=hijo,
        datos=FacilityProcessCreateAnidado(),
        tenant_id=TENANT_1,
    )
    cuantas = db.execute(
        text(
            "SELECT count(*) FROM facility_processes "
            "WHERE facility_id = :f AND process_id = :p"
        ),
        {"f": padre, "p": hijo},
    ).scalar_one()
    assert cuantas == 1


def test_el_listado_no_devuelve_lo_quitado(db: Session, par) -> None:
    padre, hijo = par
    antes = {x.process_id for x in crud.listar(db, padre)}
    assert hijo in antes

    crud.borrar(db, padre_id=padre, hijo_id=hijo)

    assert hijo not in {x.process_id for x in crud.listar(db, padre)}
