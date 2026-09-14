"""Asignar el alcance por planta, que hasta el 13-sep solo se podia con SQL.

## Que estaba roto

El alcance **se aplicaba** —`crud/base.py` filtra por las plantas de la
sesion— pero **no se podia asignar**: no habia ruta que escribiera
`user_roles.facility_id`. La pantalla de usuarios mostraba casillas de plantas
que se perdian al recargar.

## Lo que estas pruebas protegen

1. Que acotar cambie de verdad lo que `alcance_del_usuario` responde — que es lo
   que usa la guarda. Escribir la fila y que el alcance siga igual seria un
   endpoint decorativo.
2. Que se acoten **todos** los roles: con uno sin planta manda el mas amplio.
3. Que un rol nuevo **herede** la planta. Sin eso, asignarle un segundo rol a
   alguien acotado lo desacotaria en silencio.
4. Que no se pueda acotar a una planta de otra empresa (las FK no pasan RLS).
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.organization import Department, Facility, Role, User, UserRole
from app.services import usuarios as svc
from app.services.permisos import alcance_del_usuario

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EMPRESA_B = uuid.UUID("a0000000-0000-0000-0000-000000000002")
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
    s = Session(bind=conexion)
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA_A)}
    )
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


def _rol(db: Session, code: str) -> Role:
    fila = db.scalars(
        select(Role).where(Role.tenant_id == EMPRESA_A, Role.code == code)
    ).first()
    if fila is None:
        pytest.skip(f"El seed no dejo el rol {code}")
    return fila


def _planta(db: Session) -> uuid.UUID:
    fila = db.scalars(
        select(Facility).where(Facility.tenant_id == EMPRESA_A, Facility.deleted_at.is_(None))
    ).first()
    if fila is None:
        pytest.skip("El seed no dejo plantas en esta empresa")
    return fila.id


def _persona(db: Session, *roles: str) -> User:
    depto = db.scalars(
        select(Department).where(Department.tenant_id == EMPRESA_A, Department.deleted_at.is_(None))
    ).first()
    if depto is None:
        pytest.skip("El seed no dejo departamentos")
    fila = User(
        tenant_id=EMPRESA_A,
        department_id=depto.id,
        email=f"{uuid.uuid4().hex[:12]}@prueba.cl",
        full_name="Persona de prueba",
        user_type="internal",
        status="active",
    )
    db.add(fila)
    db.flush()
    for code in roles:
        db.add(UserRole(user_id=fila.id, role_id=_rol(db, code).id, tenant_id=EMPRESA_A))
    db.flush()
    # Antedatado: dentro de la transaccion `now()` esta congelado y un rol con
    # `valid_from = now()` es el caso raro de asignar y retirar a la vez.
    db.execute(
        text("UPDATE user_roles SET valid_from = now() - interval '1 day' WHERE user_id = :u"),
        {"u": str(fila.id)},
    )
    db.expire_all()
    return fila


class TestAcotarCambiaElAlcance:
    def test_acotar_a_una_planta(self, db: Session) -> None:
        persona = _persona(db, "encargado_ambiental")
        planta = _planta(db)
        assert alcance_del_usuario(db, persona.id)[0] == set()

        svc.fijar_alcance(db, persona, planta)

        assert alcance_del_usuario(db, persona.id)[0] == {planta}

    def test_se_acotan_todos_los_roles(self, db: Session) -> None:
        """Con uno sin planta manda el mas amplio: acotar uno no acota a nadie."""
        persona = _persona(db, "encargado_ambiental", "operador")
        planta = _planta(db)

        acotados = svc.fijar_alcance(db, persona, planta)

        assert acotados == 2
        assert alcance_del_usuario(db, persona.id)[0] == {planta}

    def test_null_la_deja_sin_acotar(self, db: Session) -> None:
        persona = _persona(db, "encargado_ambiental")
        svc.fijar_alcance(db, persona, _planta(db))
        svc.fijar_alcance(db, persona, None)
        assert alcance_del_usuario(db, persona.id)[0] == set()

    def test_sin_roles_no_hay_donde_guardarlo(self, db: Session) -> None:
        persona = _persona(db)
        with pytest.raises(svc.SinRolesQueAcotar):
            svc.fijar_alcance(db, persona, _planta(db))


class TestUnRolNuevoNoDesacota:
    def test_el_rol_nuevo_hereda_la_planta(self, db: Session) -> None:
        """Sin herencia, darle un segundo rol a alguien acotado lo desacotaba."""
        persona = _persona(db, "encargado_ambiental")
        planta = _planta(db)
        svc.fijar_alcance(db, persona, planta)

        svc.fijar_roles(
            db, persona, EMPRESA_A,
            [_rol(db, "encargado_ambiental").id, _rol(db, "operador").id],
        )

        assert alcance_del_usuario(db, persona.id)[0] == {planta}

    def test_sin_acotar_el_rol_nuevo_tampoco_se_acota(self, db: Session) -> None:
        persona = _persona(db, "encargado_ambiental")
        svc.fijar_roles(
            db, persona, EMPRESA_A,
            [_rol(db, "encargado_ambiental").id, _rol(db, "operador").id],
        )
        assert alcance_del_usuario(db, persona.id)[0] == set()


class TestPorHttp:
    @pytest.fixture(scope="class")
    def cliente(self):
        from fastapi.testclient import TestClient

        from app.config import get_settings
        from app.main import app

        for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
            os.environ.pop(var, None)
        get_settings.cache_clear()
        with TestClient(app) as c:
            c.headers["X-Tenant-Id"] = str(EMPRESA_A)
            yield c

    def _planta_de_b(self) -> uuid.UUID:
        engine = create_engine(URL)
        try:
            with engine.connect() as c:
                c.execute(text("SET ROLE ambienta_app"))
                c.execute(text("SELECT set_config('ambienta.tenant_id', :t, false)"), {"t": str(EMPRESA_B)})
                fid = c.execute(text("SELECT id FROM facilities WHERE deleted_at IS NULL LIMIT 1")).scalar()
        finally:
            engine.dispose()
        if fid is None:  # pragma: no cover
            pytest.skip("la empresa B no tiene plantas")
        return fid

    def test_un_cuerpo_vacio_no_amplia_el_acceso(self, cliente) -> None:
        """`null` es "todas las plantas": no puede llegar por omision.

        Contra una persona inexistente por la misma razon que la prueba de
        abajo: con el campo opcional daria 404, no escribiria."""
        r = cliente.put(f"/api/v1/users/{uuid.uuid4()}/alcance", json={})
        assert r.status_code == 422, r.text

    def test_no_se_acota_a_una_planta_de_otra_empresa(self, cliente) -> None:
        """**Contra una persona inexistente, a proposito.** El 13-sep la prueba de
        mutacion de esta guarda —sin ella, contra una persona real— dejo a
        alguien de la empresa A acotado a una planta de la B, en la base de
        desarrollo. Asi, con la guarda da 422 y sin ella 404: distingue igual y
        no puede escribir."""
        r = cliente.put(
            f"/api/v1/users/{uuid.uuid4()}/alcance",
            json={"facility_id": str(self._planta_de_b())},
        )
        assert r.status_code == 422, r.text

    def test_leer_el_alcance_de_alguien_inexistente_es_404(self, cliente) -> None:
        r = cliente.get(f"/api/v1/users/{uuid.uuid4()}/alcance")
        assert r.status_code == 404, r.text
