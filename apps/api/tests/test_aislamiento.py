"""El aislamiento entre empresas depende de una sola linea, y hay que saberlo.

Ninguna consulta de la aplicacion filtra por `tenant_id`: ni `CRUDBase` ni un
solo router. Se comprobo sobre el codigo. O sea que Row Level Security no es la
"segunda barrera" — **es la unica**, y por eso conviene que sea solida.

Hasta el 10-ago-2026 la API se conectaba con el dueno de la base, superusuario
con BYPASSRLS, y lo unico que la protegia era el `SET LOCAL ROLE ambienta_app`
de cada transaccion. Se perdia en cada commit. Medido entonces:

    conexion            olvidando todo   con tenant   tras commit
    dueno (superusuario)        6              4            6
    rol de aplicacion           0              4            0

Ahora la conexion usa el rol acotado, asi que el modo de fallo se invirtio: de
"ve todo" a "no ve nada". Estas pruebas fijan esa propiedad.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TENANT_1 = "a0000000-0000-0000-0000-000000000001"
TENANT_2 = "a0000000-0000-0000-0000-000000000002"
# El rol de la aplicacion, el mismo con el que se conecta la API. Probar con el
# dueno de la base daria falsos verdes: es superusuario y salta RLS.
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
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _fijar(sesion: Session, tenant: str) -> None:
    sesion.execute(text("SET LOCAL ROLE ambienta_app"))
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": tenant}
    )


def _usuarios(sesion: Session) -> int:
    return sesion.execute(text("SELECT count(*) FROM users")).scalar_one()


def test_cada_empresa_ve_solo_lo_suyo(db: Session) -> None:
    _fijar(db, TENANT_1)
    del_uno = _usuarios(db)
    db.rollback()

    _fijar(db, TENANT_2)
    del_dos = _usuarios(db)

    total = db.execute(
        text("SELECT count(*) FROM users")  # sigue acotado por RLS
    ).scalar_one()
    assert del_uno > 0 and del_dos > 0
    assert del_uno + del_dos > total, (
        "Cada empresa deberia ver un subconjunto propio; si una ve el total, "
        "RLS no esta filtrando."
    )


def test_sin_declarar_tenant_no_se_ve_nada(db: Session) -> None:
    """Falla cerrado: una pantalla vacia es preferible a una fuga."""
    db.execute(text("SET LOCAL ROLE ambienta_app"))
    db.execute(text("SELECT set_config('ambienta.tenant_id', '', true)"))
    assert _usuarios(db) == 0


def test_la_conexion_por_si_sola_ya_aisla(db: Session) -> None:
    """La propiedad que se gano al dejar de conectarse con un superusuario.

    Sin `SET LOCAL ROLE` y sin declarar tenant —un endpoint mal escrito, o una
    consulta puesta despues de un commit— la respuesta es cero filas. Antes era
    todas las empresas, y sin ningun aviso.
    """
    assert _usuarios(db) == 0, (
        "La conexion vio filas sin declarar tenant. Revisar que DATABASE_URL "
        "use `ambienta_app` y que ese rol no sea superusuario ni tenga "
        "BYPASSRLS: si puede saltarse RLS, no hay aislamiento."
    )


def test_el_rol_de_la_conexion_no_puede_saltarse_rls(db: Session) -> None:
    """Lo que hace cierto a todo lo demas. Si esto cambia, nada protege."""
    fila = db.execute(
        text(
            "SELECT rolsuper OR rolbypassrls FROM pg_roles "
            "WHERE rolname = current_user"
        )
    ).scalar_one()
    assert fila is False, (
        "La API se conecta con un rol que ignora Row Level Security. "
        "Las policies existen pero no se evaluan."
    )


def test_no_se_puede_escribir_en_otra_empresa(db: Session) -> None:
    _fijar(db, TENANT_1)
    with pytest.raises(Exception, match="row-level security"):
        db.execute(
            text(
                "INSERT INTO users (tenant_id, email, full_name, user_type, status) "
                "VALUES (:t, 'intruso@x.cl', 'X', 'internal', 'active')"
            ),
            {"t": TENANT_2},
        )


def test_el_registro_de_auditoria_no_se_puede_alterar(db: Session) -> None:
    """RNF-25. La inmutabilidad la sostiene la base, no la aplicacion."""
    _fijar(db, TENANT_1)
    with pytest.raises(Exception):
        db.execute(text("UPDATE audit_log SET action = 'alterado'"))
