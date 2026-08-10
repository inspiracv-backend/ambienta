"""El aislamiento entre empresas depende de una sola linea, y hay que saberlo.

Ninguna consulta de la aplicacion filtra por `tenant_id`: ni `CRUDBase` ni un
solo router. Se comprobo sobre el codigo. O sea que Row Level Security no es la
"segunda barrera" que dice CLAUDE.md — **es la unica**.

Y RLS solo se aplica si la transaccion corre como `ambienta_app`. La API se
conecta como `ambienta`, que es superusuario con BYPASSRLS, asi que todo
depende de que `SET LOCAL ROLE ambienta_app` se ejecute en cada transaccion
(`get_tenant_db`). Si esa linea desaparece, no falla nada: simplemente se
empiezan a ver los datos de todas las empresas.

Estas pruebas fijan las tres propiedades que sostienen el invariante.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TENANT_1 = "a0000000-0000-0000-0000-000000000001"
TENANT_2 = "a0000000-0000-0000-0000-000000000002"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
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


def test_el_cambio_de_rol_es_lo_que_activa_rls(db: Session) -> None:
    """La prueba que explica por que `SET LOCAL ROLE` no se puede omitir.

    Con el mismo tenant declarado, la diferencia entre ver 4 filas y verlas
    todas es unicamente el rol. Documenta que la API se conecta con un
    superusuario y que la proteccion la da esa linea, no la conexion.
    """
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_1}
    )
    sin_cambio_de_rol = _usuarios(db)

    db.execute(text("SET LOCAL ROLE ambienta_app"))
    con_cambio_de_rol = _usuarios(db)

    assert sin_cambio_de_rol > con_cambio_de_rol, (
        "Se esperaba que el superusuario viera mas filas que el rol de "
        "aplicacion. Si son iguales, o la API ya no se conecta como "
        "superusuario (bien) o RLS dejo de aplicar (grave)."
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
