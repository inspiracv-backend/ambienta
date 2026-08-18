"""El permiso efectivo, y sobre todo su regla de precedencia (RF-08, RF-12).

Spec: `openspec/changes/sistema-actores-roles-rbac/specs/rbac/spec.md`.

La propiedad que importa es una sola y es facil de romper sin notarlo: **una
denegacion individual gana sobre lo que conceda cualquier rol**. Si alguien
invierte el orden —denegar primero y unir despues— los casos de "el rol
concede" y "la excepcion concede" siguen pasando, y solo falla aquel en que se
contradicen. Ese caso esta cubierto aca a proposito.

Necesitan base con el esquema cargado. Sin ella se saltan, igual que
`test_aislamiento.py`.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.permisos import (
    alcance_del_usuario,
    excepciones_del_usuario,
    permisos_de_roles,
    permisos_efectivos,
    tiene_permiso,
)

TENANT = "a0000000-0000-0000-0000-000000000001"
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
    sesion.execute(text("SET LOCAL ROLE ambienta_app"))
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT}
    )
    try:
        yield sesion
    finally:
        # Siempre rollback: estas pruebas escriben roles y permisos, y dejarlos
        # cambiaria el resultado de las que corran despues.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _permiso(db: Session) -> tuple[int, str]:
    """Un permiso cualquiera del catalogo sembrado, con su id y su codigo."""
    fila = db.execute(text("SELECT id, code FROM permissions ORDER BY id LIMIT 1")).first()
    if fila is None:
        pytest.skip("El catalogo de permisos esta vacio")
    return fila[0], fila[1]


def _usuario(db: Session) -> uuid.UUID:
    uid = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO users (id, tenant_id, email, full_name, user_type, status) "
            "VALUES (:i, :t, :e, 'Prueba Permisos', 'internal', 'active')"
        ),
        {"i": uid, "t": TENANT, "e": f"permisos-{uid}@prueba.cl"},
    )
    return uid


def _rol_con(db: Session, permission_id: int) -> uuid.UUID:
    rid = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO roles (id, tenant_id, code, name) "
            "VALUES (:i, :t, :c, 'Rol de prueba')"
        ),
        {"i": rid, "t": TENANT, "c": f"prueba-{rid}"},
    )
    db.execute(
        text(
            "INSERT INTO role_permissions (role_id, permission_id, granted) "
            "VALUES (:r, :p, true)"
        ),
        {"r": rid, "p": permission_id},
    )
    return rid


def _rol_sin(db: Session, permission_id: int) -> uuid.UUID:
    """Un rol con una fila que **niega** ese permiso (`granted = false`)."""
    rid = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO roles (id, tenant_id, code, name) "
            "VALUES (:i, :t, :c, 'Rol que niega')"
        ),
        {"i": rid, "t": TENANT, "c": f"niega-{rid}"},
    )
    db.execute(
        text(
            "INSERT INTO role_permissions (role_id, permission_id, granted) "
            "VALUES (:r, :p, false)"
        ),
        {"r": rid, "p": permission_id},
    )
    return rid


def _asignar(db: Session, uid, rid, facility=None, desde=None, hasta=None) -> None:
    """Asigna un rol, opcionalmente acotado y con vigencia explicita.

    `desde` se pasa junto con `hasta` porque el esquema exige
    `valid_to > valid_from`: un rol ya vencido tiene que haber **empezado**
    antes, no solo terminado. Dejar `valid_from` en su valor por defecto —ahora—
    y poner una fecha de termino pasada viola el CHECK, que es correcto: seria
    un rol que termina antes de empezar.
    """
    db.execute(
        text(
            "INSERT INTO user_roles "
            "(user_id, role_id, tenant_id, facility_id, valid_from, valid_to) "
            "VALUES (:u, :r, :t, :f, COALESCE(CAST(:d AS timestamptz), now()), :v)"
        ),
        {"u": uid, "r": rid, "t": TENANT, "f": facility, "d": desde, "v": hasta},
    )


def _excepcion(db: Session, uid, permission_id: int, granted: bool) -> None:
    db.execute(
        text(
            "INSERT INTO user_permissions "
            "(user_id, permission_id, tenant_id, granted, reason) "
            "VALUES (:u, :p, :t, :g, 'prueba')"
        ),
        {"u": uid, "p": permission_id, "t": TENANT, "g": granted},
    )


def _una_planta(db: Session):
    planta = db.execute(
        text("SELECT id FROM facilities WHERE deleted_at IS NULL LIMIT 1")
    ).scalar()
    if planta is None:
        pytest.skip("Sin instalaciones sembradas")
    return planta


class TestPrecedencia:
    """La regla que le da sentido al modelo entero."""

    def test_la_denegacion_individual_gana_sobre_el_rol(self, db: Session) -> None:
        """La propiedad util del modelo: quitar un permiso sin tocar el rol.

        Nota sobre el orden de las operaciones: invertirlo **no** cambia el
        resultado, porque la clave primaria de `user_permissions` impide que un
        permiso este concedido y denegado a la vez. Se comprobo rompiendolo a
        proposito y el resultado es identico. Lo que este test protege es que
        la denegacion se aplique sobre lo que concede el rol, no el orden.
        """
        pid, codigo = _permiso(db)
        uid = _usuario(db)
        _asignar(db, uid, _rol_con(db, pid))
        _excepcion(db, uid, pid, granted=False)

        assert codigo in permisos_de_roles(db, uid), "el rol si lo concede"
        assert not tiene_permiso(db, uid, codigo), "la denegacion tiene que ganar"

    def test_la_concesion_individual_suma_sobre_lo_que_el_rol_no_da(
        self, db: Session
    ) -> None:
        pid, codigo = _permiso(db)
        uid = _usuario(db)
        _excepcion(db, uid, pid, granted=True)

        assert codigo not in permisos_de_roles(db, uid)
        assert tiene_permiso(db, uid, codigo)

    def test_un_rol_que_niega_explicitamente_no_concede(self, db: Session) -> None:
        """`role_permissions.granted = false` es una fila que dice "este rol NO".

        Existe la columna, asi que existe el caso. Sin esta prueba, tratar
        todas las filas como concesion —ignorando `granted`— pasa desapercibido,
        y un rol configurado para negar terminaria otorgando.
        """
        pid, codigo = _permiso(db)
        uid = _usuario(db)
        rid = _rol_sin(db, pid)
        _asignar(db, uid, rid)

        assert codigo not in permisos_de_roles(db, uid)
        assert not tiene_permiso(db, uid, codigo)

    def test_sin_rol_ni_excepcion_no_tiene_nada(self, db: Session) -> None:
        """Cerrado por defecto: lo que no se concedio, no se puede."""
        _, codigo = _permiso(db)
        uid = _usuario(db)

        assert permisos_efectivos(db, uid) == set()
        assert not tiene_permiso(db, uid, codigo)


class TestVigencia:
    def test_un_rol_vencido_no_concede_nada(self, db: Session) -> None:
        """La diferencia entre "fue encargado" y "es encargado".

        Sin el filtro de vigencia alguien conserva sus permisos despues de que
        se le retiraron, y el retiro parece aplicado porque la fila existe.
        """
        pid, codigo = _permiso(db)
        uid = _usuario(db)
        _asignar(
            db,
            uid,
            _rol_con(db, pid),
            desde="2019-01-01T00:00:00Z",
            hasta="2020-01-01T00:00:00Z",
        )

        assert codigo not in permisos_de_roles(db, uid)
        assert not tiene_permiso(db, uid, codigo)

    def test_un_rol_sin_fecha_de_termino_sigue_vigente(self, db: Session) -> None:
        pid, codigo = _permiso(db)
        uid = _usuario(db)
        _asignar(db, uid, _rol_con(db, pid))

        assert tiene_permiso(db, uid, codigo)


class TestAlcance:
    def test_un_rol_acotado_a_una_planta_declara_esa_planta(self, db: Session) -> None:
        pid, _ = _permiso(db)
        uid = _usuario(db)
        planta = _una_planta(db)
        _asignar(db, uid, _rol_con(db, pid), facility=planta)

        instalaciones, _departamentos = alcance_del_usuario(db, uid)
        assert instalaciones == {planta}

    def test_sin_acotar_devuelve_vacio_que_significa_todo(self, db: Session) -> None:
        """Vacio es "sin acotar", no "ninguna".

        Confundirlas dejaria a los administradores —que no tienen rol de
        planta— sin ver nada, que es el error mas caro posible en esta funcion.
        """
        pid, _ = _permiso(db)
        uid = _usuario(db)
        _asignar(db, uid, _rol_con(db, pid))

        assert alcance_del_usuario(db, uid) == (set(), set())

    def test_un_rol_global_ensancha_a_uno_acotado(self, db: Session) -> None:
        """El rol mas amplio manda.

        Quien tiene un rol de planta y ademas uno global no esta acotado a esa
        planta: tener un rol global es justamente no estarlo.
        """
        pid, _ = _permiso(db)
        uid = _usuario(db)
        planta = _una_planta(db)
        _asignar(db, uid, _rol_con(db, pid), facility=planta)
        _asignar(db, uid, _rol_con(db, pid))

        assert alcance_del_usuario(db, uid) == (set(), set())


class TestExcepciones:
    def test_concedidas_y_denegadas_vienen_separadas(self, db: Session) -> None:
        """Mezclarlas obligaria a recalcular la precedencia en cada uso."""
        pid, codigo = _permiso(db)
        uid = _usuario(db)
        _excepcion(db, uid, pid, granted=False)

        concedidas, denegadas = excepciones_del_usuario(db, uid)
        assert codigo in denegadas
        assert codigo not in concedidas
