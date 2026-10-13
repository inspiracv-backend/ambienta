"""El primer Admin Global: sin el, en produccion nadie puede dar de alta una empresa.

La sesion va con savepoints y se revierte entera; Clerk va simulado, porque
correr la suite mandaria invitaciones de verdad.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.organization import Role, Tenant, User
from app.services import invitacion_de_usuario as svc_invitacion
from app.services.clave_local import ClerkNoDisponible
from app.services.permisos import permisos_efectivos
from app.tareas import crear_admin_global as tarea
from app.tareas.__main__ import main

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def s():
    engine = create_engine(URL)
    try:
        con = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible ({exc}).")
    trans = con.begin()
    sesion = Session(bind=con, join_transaction_mode="create_savepoint")
    sesion.execute(text("SET LOCAL ROLE ambienta_app"))
    try:
        yield sesion
    finally:
        sesion.close()
        trans.rollback()
        con.close()
        engine.dispose()


@pytest.fixture
def clerk(monkeypatch):
    llamadas: list[dict] = []

    def falso(metodo, ruta, cuerpo=None):
        llamadas.append(cuerpo or {})
        return {"id": "inv_admin"}

    monkeypatch.setattr(svc_invitacion, "_clerk", falso)
    return llamadas


@pytest.fixture(autouse=True)
def sin_plataforma_previa(s):
    """Las pruebas parten de "no hay plataforma", que es el estado de produccion.

    Si la base de desarrollo ya tuviera una, se retira **dentro de la transaccion
    de la prueba**, que se revierte al terminar.
    """
    for t in s.scalars(select(Tenant).where(Tenant.tenant_type == "platform")).all():
        t.tenant_type = "company"
    s.flush()


def _rut() -> str:
    return f"95{uuid.uuid4().int % 1_000_000:06d}-4"


def _correo() -> str:
    return f"admin-global-{uuid.uuid4().hex[:8]}@prueba.cl"


def _declarar(s: Session, tenant_id: uuid.UUID) -> None:
    s.execute(text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(tenant_id)})


def test_crea_la_plataforma_y_al_admin_con_su_invitacion(s, clerk) -> None:
    correo = _correo()

    r = tarea.crear(s, correo=correo, nombre="Ana Admin", razon_social="Ambienta SpA", rut=_rut())

    _declarar(s, r.tenant_id)
    empresa = s.get(Tenant, r.tenant_id)
    admin = s.get(User, r.usuario_id)
    assert r.empresa_nueva and empresa.tenant_type == "platform"
    assert admin.user_type == "platform_admin" and admin.status == "invited"
    assert admin.email == correo
    # Lo que decide si puede dar de alta empresas: `POST /tenants/` pide
    # `company_profile.write` a la guarda de rutas.
    assert "company_profile.write" in permisos_efectivos(s, admin.id)
    assert "role.manage" in permisos_efectivos(s, admin.id)
    assert clerk[0]["public_metadata"] == {"tenant_id": str(r.tenant_id)}
    assert len(s.scalars(select(Role).where(Role.tenant_id == r.tenant_id)).all()) == 4


def test_si_ya_hay_un_admin_global_se_niega_sin_llamar_a_Clerk(s, clerk) -> None:
    tarea.crear(s, correo=_correo(), nombre="Primera", razon_social="Ambienta SpA", rut=_rut())

    with pytest.raises(tarea.YaHayAdminGlobal):
        tarea.crear(s, correo=_correo(), nombre="Segunda")

    assert len(clerk) == 1, "el segundo intento mando una invitacion"


def test_sin_plataforma_y_sin_RUT_no_inventa_uno(s, clerk) -> None:
    with pytest.raises(tarea.ErrorDeArranque, match="RUT"):
        tarea.crear(s, correo=_correo(), nombre="Sin RUT")

    assert clerk == []


def test_reusa_la_empresa_de_la_plataforma_que_ya_existe(s, clerk) -> None:
    existente = Tenant(
        country_id=1, tenant_type="platform", rut_tax_id=_rut(), legal_name="Ambienta SpA"
    )
    s.add(existente)
    s.flush()

    r = tarea.crear(s, correo=_correo(), nombre="Ana Admin")

    assert r.tenant_id == existente.id and not r.empresa_nueva


def test_si_Clerk_no_responde_no_queda_la_plataforma(s, monkeypatch) -> None:
    def sin_clave(metodo, ruta, cuerpo=None):
        raise ClerkNoDisponible("Falta CLERK_SECRET_KEY")

    monkeypatch.setattr(svc_invitacion, "_clerk", sin_clave)
    rut = _rut()

    with pytest.raises(ClerkNoDisponible):
        tarea.crear(s, correo=_correo(), nombre="Ana", razon_social="Ambienta SpA", rut=rut)
    s.rollback()  # lo que hace el despachador

    assert s.scalar(select(Tenant).where(Tenant.rut_tax_id == rut)) is None


def test_el_comando_documentado_existe() -> None:
    """La leccion de `sincronizar_bcn`: el comando del README no existia y salia con 0."""
    with pytest.raises(SystemExit) as e:
        main(["crear-admin-global", "--help"])
    assert e.value.code == 0
