"""Dar de alta una empresa y que su administrador pueda entrar.

## Lo que estaba roto, medido el 14-sep

Ninguna empresa creada desde la plataforma podia tener a nadie trabajando:

| pieza | que pasaba |
|---|---|
| roles | `db/09` los siembra con `CROSS JOIN tenants`; en produccion corre con cero empresas. Toda empresa nacia **sin roles**: 403 en todo |
| administrador | exigia departamento (`ck_users_interno_con_departamento`), y los departamentos los crea **el** administrador |
| invitacion | la pantalla hacia `POST /users/` y nunca pedia la invitacion a Clerk: la persona no recibia correo |

## Como se prueba

La sesion va enganchada con savepoints: el `commit` del handler cierra el
savepoint y la transaccion de afuera se revierte entera, asi que no queda una
empresa de prueba en la base. Clerk va simulado — una prueba que sale a la red
mandaria invitaciones de verdad.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.organization import Permission, Role, RolePermission, Tenant, User
from app.routers.tenants import create_tenant
from app.routers.users import invitar_persona
from app.schemas.organization import AdministradorInicial, AltaDeEmpresa, InvitarPersona
from app.services import invitacion_de_usuario as svc_invitacion
from app.services import roles_de_sistema as svc_roles
from app.services.clave_local import ClerkNoDisponible, ErrorDeClaveLocal
from app.services.permisos import permisos_efectivos

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
MIGRACION_ROLES = Path(__file__).resolve().parents[3] / "db" / "09_roles_por_codigo.sql"


@pytest.fixture
def conexion():
    engine = create_engine(URL)
    try:
        con = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible ({exc}).")
    trans = con.begin()
    try:
        yield con
    finally:
        trans.rollback()
        con.close()
        engine.dispose()


@pytest.fixture
def clerk(monkeypatch):
    """Lo que se le manda a Clerk, sin salir a la red."""
    llamadas: list[dict] = []

    def falso(metodo, ruta, cuerpo=None):
        llamadas.append(cuerpo or {})
        return {"id": "inv_prueba"}

    monkeypatch.setattr(svc_invitacion, "_clerk", falso)
    return llamadas


def _sesion(con) -> Session:
    s = Session(bind=con, join_transaction_mode="create_savepoint")
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    return s


def _declarar(s: Session, tenant_id: uuid.UUID) -> None:
    s.execute(text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(tenant_id)})


def _rut() -> str:
    return f"96{uuid.uuid4().int % 1_000_000:06d}-3"


def _correo() -> str:
    return f"alta-{uuid.uuid4().hex[:10]}@prueba.cl"


def _catalogo(s: Session) -> list[str]:
    return list(s.scalars(select(Permission.code)).all())


def _permisos_del_rol(s: Session, tenant_id: uuid.UUID, codigo: str) -> set[str]:
    return set(
        s.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.tenant_id == tenant_id, Role.code == codigo, RolePermission.granted)
        ).all()
    )


# ── Roles de sistema ──────────────────────────────────────────────────────


class TestLosRolesDeSistema:
    def test_una_empresa_nueva_arranca_SIN_roles(self, conexion) -> None:
        """La linea base del defecto: si falla, el resto comprueba algo que ya
        no pasa."""
        s = _sesion(conexion)
        t = Tenant(country_id=1, tenant_type="company", rut_tax_id=_rut(), legal_name="Base SpA")
        s.add(t)
        s.flush()
        _declarar(s, t.id)

        assert s.scalars(select(Role).where(Role.tenant_id == t.id)).all() == []

    def test_las_reglas_reproducen_los_roles_de_una_empresa_sembrada(self, conexion) -> None:
        """**El medidor antes que el resultado.** Las reglas en Python tienen que
        dar exactamente lo que `db/09` dejo en la empresa A; si no, sembrarian
        permisos distintos segun cuando nacio la empresa."""
        s = _sesion(conexion)
        _declarar(s, EMPRESA_A)
        catalogo = _catalogo(s)

        for codigo, _, _ in svc_roles.ROLES:
            en_la_base = _permisos_del_rol(s, EMPRESA_A, codigo)
            if not en_la_base:  # pragma: no cover
                pytest.skip(f"La empresa A no tiene el rol {codigo}")
            assert svc_roles.permisos_de(codigo, catalogo) == en_la_base, codigo

    def test_sembrar_dos_veces_no_duplica(self, conexion) -> None:
        s = _sesion(conexion)
        t = Tenant(country_id=1, tenant_type="company", rut_tax_id=_rut(), legal_name="Doble SpA")
        s.add(t)
        s.flush()
        _declarar(s, t.id)

        assert svc_roles.sembrar_roles_de_sistema(s, t.id) == 4
        assert svc_roles.sembrar_roles_de_sistema(s, t.id) == 0
        assert len(s.scalars(select(Role).where(Role.tenant_id == t.id)).all()) == 4

    @pytest.mark.parametrize(
        ("codigo", "constante"),
        [
            ("encargado_ambiental", svc_roles.PERMISOS_ENCARGADO),
            ("operador", svc_roles.PERMISOS_OPERADOR),
        ],
    )
    def test_las_listas_son_las_de_db_09(self, codigo: str, constante: frozenset[str]) -> None:
        sql = MIGRACION_ROLES.read_text(encoding="utf-8")
        bloque = sql.split(f"WHERE r.code = '{codigo}'", 1)[1].split("ON CONFLICT", 1)[0]
        assert set(re.findall(r"'([a-z_.]+)'", bloque)) == constante


# ── Invitar a una persona (POST /users/invitaciones) ──────────────────────


class TestInvitarUnaPersona:
    def _invitar(self, s: Session, **cambios):
        cuerpo = {
            # El cuerpo literal de `lib/users-store.tsx::inviteUser`.
            "full_name": "Carolina Pérez",
            "email": _correo(),
            "user_type": "tenant_admin",
            "department_id": None,
            "role_code": "admin_empresa",
        }
        cuerpo.update(cambios)
        return invitar_persona(datos=InvitarPersona(**cuerpo), tenant_id=EMPRESA_A, db=s)

    def test_queda_invitada_CON_su_rol_y_Clerk_recibe_la_empresa(self, conexion, clerk) -> None:
        s = _sesion(conexion)
        _declarar(s, EMPRESA_A)

        r = self._invitar(s)

        _declarar(s, EMPRESA_A)
        assert r.user.status == "invited"
        assert r.clerk_invitation_id == "inv_prueba"
        assert clerk[0]["public_metadata"] == {"tenant_id": str(EMPRESA_A)}
        assert "user.write" in permisos_efectivos(s, r.user.id), "entro sin permisos"

    def test_si_Clerk_rechaza_NO_queda_la_fila(self, conexion, monkeypatch) -> None:
        """El defecto de fondo: una fila sin invitacion ocupa el correo —que es
        unico— y no puede entrar nunca."""
        def rechaza(metodo, ruta, cuerpo=None):
            raise ErrorDeClaveLocal("el correo no tiene un formato valido")

        monkeypatch.setattr(svc_invitacion, "_clerk", rechaza)
        s = _sesion(conexion)
        _declarar(s, EMPRESA_A)
        correo = _correo()

        with pytest.raises(HTTPException) as e:
            self._invitar(s, email=correo)
        s.rollback()  # lo que hace `get_tenant_db` al cerrar sin commit

        assert e.value.status_code == 422
        _declarar(s, EMPRESA_A)
        assert s.scalar(select(User).where(User.email == correo)) is None

    def test_sin_CLERK_SECRET_KEY_responde_503_y_no_escribe(self, conexion, monkeypatch) -> None:
        def sin_clave(metodo, ruta, cuerpo=None):
            raise ClerkNoDisponible("Falta CLERK_SECRET_KEY")

        monkeypatch.setattr(svc_invitacion, "_clerk", sin_clave)
        s = _sesion(conexion)
        _declarar(s, EMPRESA_A)
        correo = _correo()

        with pytest.raises(HTTPException) as e:
            self._invitar(s, email=correo)
        s.rollback()

        assert e.value.status_code == 503
        _declarar(s, EMPRESA_A)
        assert s.scalar(select(User).where(User.email == correo)) is None

    def test_un_rol_que_la_empresa_no_tiene_se_rechaza_ANTES_de_Clerk(
        self, conexion, clerk
    ) -> None:
        s = _sesion(conexion)
        _declarar(s, EMPRESA_A)

        with pytest.raises(HTTPException) as e:
            self._invitar(s, role_code="rol_inventado")

        assert e.value.status_code == 422
        assert clerk == [], "se mando una invitacion con un rol inexistente"

    def test_un_interno_sin_departamento_no_llega_a_Clerk(self, conexion, clerk) -> None:
        """RF-11 sigue en pie para `internal`: el CHECK salta en el `flush`, que
        va antes de hablar con Clerk."""
        s = _sesion(conexion)
        _declarar(s, EMPRESA_A)

        with pytest.raises(Exception) as e:
            self._invitar(s, user_type="internal", role_code="encargado_ambiental")

        assert "ck_users_interno_con_departamento" in str(e.value)
        assert clerk == []

    def test_otro_tipo_de_cuenta_no_se_invita(self, conexion, clerk) -> None:
        s = _sesion(conexion)
        _declarar(s, EMPRESA_A)

        with pytest.raises(HTTPException) as e:
            self._invitar(s, user_type="platform_admin")

        assert e.value.status_code == 422
        assert clerk == []


# ── Alta de empresa con su administrador (POST /tenants/) ─────────────────


class TestAltaDeEmpresaConAdministrador:
    def test_nace_con_roles_y_con_su_administrador_invitado(self, conexion, clerk) -> None:
        s = _sesion(conexion)
        correo = _correo()

        creada = create_tenant(
            data=AltaDeEmpresa(
                country_id=1,
                rut_tax_id=_rut(),
                legal_name="Áridos del Maule SpA",
                administrador=AdministradorInicial(full_name="Rosa Muñoz", email=correo),
            ),
            _=None,
            db=s,
        )

        _declarar(s, creada.id)
        codigos = set(s.scalars(select(Role.code).where(Role.tenant_id == creada.id)).all())
        assert codigos == {c for c, _, _ in svc_roles.ROLES}

        admin = s.scalar(select(User).where(User.email == correo))
        assert admin is not None and admin.tenant_id == creada.id
        assert admin.user_type == "tenant_admin" and admin.department_id is None
        assert admin.status == "invited"
        # Lo que decide si puede trabajar: que su rol le de permisos de verdad.
        assert "company_profile.write" in permisos_efectivos(s, admin.id)
        assert clerk[0]["public_metadata"] == {"tenant_id": str(creada.id)}

    def test_si_la_invitacion_no_sale_la_empresa_tampoco_se_crea(
        self, conexion, monkeypatch
    ) -> None:
        def sin_clave(metodo, ruta, cuerpo=None):
            raise ClerkNoDisponible("Falta CLERK_SECRET_KEY")

        monkeypatch.setattr(svc_invitacion, "_clerk", sin_clave)
        s = _sesion(conexion)
        rut = _rut()

        with pytest.raises(HTTPException) as e:
            create_tenant(
                data=AltaDeEmpresa(
                    country_id=1,
                    rut_tax_id=rut,
                    legal_name="A medias SpA",
                    administrador=AdministradorInicial(full_name="Nadie", email=_correo()),
                ),
                _=None,
                db=s,
            )
        s.rollback()

        assert e.value.status_code == 503
        assert s.scalar(select(Tenant).where(Tenant.rut_tax_id == rut)) is None

    def test_sin_administrador_sigue_funcionando_y_siembra_roles(self, conexion, clerk) -> None:
        s = _sesion(conexion)

        creada = create_tenant(
            data=AltaDeEmpresa(country_id=1, rut_tax_id=_rut(), legal_name="Sola SpA"),
            _=None,
            db=s,
        )

        _declarar(s, creada.id)
        assert len(s.scalars(select(Role).where(Role.tenant_id == creada.id)).all()) == 4
        assert clerk == []
