"""El borrado del CRUD es logico y las lecturas lo respetan.

Corre contra Postgres real, no contra dobles: lo que se comprueba es que la
fila quede marcada y deje de aparecer, y eso depende del `WHERE` que llega a la
base. Un doble en memoria confirmaria que llamamos a nuestro propio codigo.

Cada prueba termina en `rollback()`, asi que se pueden ejecutar sobre una base
con datos sin dejar rastro.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.crud.iso14001 import crud_environmental_aspect
from app.crud.organization import crud_facility
from app.models.iso14001 import EnvironmentalAspect

TENANT = "a0000000-0000-0000-0000-000000000001"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    """Sesion con el tenant fijado, igual que la que arma `get_tenant_db`."""
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")

    sesion = Session(bind=conexion)
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _crear_aspecto(db: Session) -> EnvironmentalAspect:
    instalacion = crud_facility.get_multi(db, limit=1)[0]
    obj = EnvironmentalAspect(
        tenant_id=uuid.UUID(TENANT),
        facility_id=instalacion.id,
        activity="Prueba de borrado logico",
        aspect="Consumo de agua",
        impact_type="resource_depletion",
    )
    db.add(obj)
    db.flush()
    return obj


def test_el_modelo_declara_que_usa_borrado_logico() -> None:
    assert crud_environmental_aspect.usa_borrado_logico is True


def test_remove_marca_la_fila_en_vez_de_eliminarla(db: Session) -> None:
    obj = _crear_aspecto(db)
    identificador = obj.id

    crud_environmental_aspect.remove(db, id=identificador)

    # La fila sigue en la tabla: es lo que distingue el borrado logico del
    # fisico, y lo que mantiene con sentido las referencias del audit log.
    sigue = db.execute(
        text("SELECT deleted_at FROM environmental_aspects WHERE id = :i"),
        {"i": identificador},
    ).first()
    assert sigue is not None
    assert sigue[0] is not None


def test_lo_borrado_desaparece_de_get(db: Session) -> None:
    obj = _crear_aspecto(db)
    assert crud_environmental_aspect.get(db, obj.id) is not None

    crud_environmental_aspect.remove(db, id=obj.id)

    assert crud_environmental_aspect.get(db, obj.id) is None


def test_lo_borrado_desaparece_de_los_listados(db: Session) -> None:
    """Es la mitad que faltaba: sin esto el borrado no se notaria en pantalla."""
    obj = _crear_aspecto(db)
    ids_antes = {x.id for x in crud_environmental_aspect.get_multi(db, limit=500)}
    assert obj.id in ids_antes

    crud_environmental_aspect.remove(db, id=obj.id)

    ids_despues = {x.id for x in crud_environmental_aspect.get_multi(db, limit=500)}
    assert obj.id not in ids_despues


def test_borrar_dos_veces_no_es_un_error(db: Session) -> None:
    obj = _crear_aspecto(db)
    assert crud_environmental_aspect.remove(db, id=obj.id) is not None
    assert crud_environmental_aspect.remove(db, id=obj.id) is None


def test_borrar_algo_inexistente_devuelve_none(db: Session) -> None:
    assert crud_environmental_aspect.remove(db, id=uuid.uuid4()) is None


def test_un_modelo_con_clave_compuesta_falla_con_un_mensaje_util(db: Session) -> None:
    """`EquipmentOperator` se direcciona por (equipment_id, user_id).

    Hoy no lo usa ningun router. Si alguien lo conecta, tiene que enterarse por
    un mensaje que diga que hacer y no por un AttributeError a mitad de una
    consulta.
    """
    from app.crud.iso14001 import crud_equipment_operator

    with pytest.raises(NotImplementedError, match="clave es compuesta|compuesta"):
        crud_equipment_operator.get(db, uuid.uuid4())


def test_no_se_pisa_la_fecha_del_primer_borrado(db: Session) -> None:
    """La fecha dice cuando se borro; un segundo intento no la mueve."""
    obj = _crear_aspecto(db)
    crud_environmental_aspect.remove(db, id=obj.id)
    primera = db.execute(
        text("SELECT deleted_at FROM environmental_aspects WHERE id = :i"),
        {"i": obj.id},
    ).scalar_one()

    crud_environmental_aspect.remove(db, id=obj.id)

    segunda = db.execute(
        text("SELECT deleted_at FROM environmental_aspects WHERE id = :i"),
        {"i": obj.id},
    ).scalar_one()
    assert primera == segunda
