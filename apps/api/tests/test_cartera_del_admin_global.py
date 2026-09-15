"""El Admin Global ve su cartera y administra lo que decide la plataforma.

## Lo que estaba roto, medido el 14-sep

- Con Clerk, `GET /tenants/` le devolvia al Admin Global **una sola empresa**:
  la de la plataforma. Su pantalla de gestion de empresas se veia con una fila.
- `_es_admin_global` buscaba a quien llama con `get_db`, que no declara
  empresa, y `users` lleva RLS. **Funcionaba de rebote**: la guarda de rutas
  declara la empresa en la misma sesion. Ahora se declara aca, para que quitar
  la guarda no lo deje en cero filas sin avisar.
- Una empresa podia cambiarse sola el estado, el tope de usuarios y los modulos.

## Por que se simula Clerk

Las guardas viven detras de `clerk_configured`, y el resto de la suite corre en
modo desarrollo. Sin simularlo estas reglas estarian escritas y sin ejecutarse,
que es lo que advierte `test_admin_global_no_edita.py`.
"""
from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.models.organization import Tenant, User
from app.routers import tenants as router
from app.schemas.organization import TenantUpdate

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EMPRESA_B = uuid.UUID("a0000000-0000-0000-0000-000000000002")


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
    if sesion.get(Tenant, EMPRESA_B) is None:  # pragma: no cover
        pytest.skip("El seed no tiene la empresa B")
    try:
        yield sesion
    finally:
        sesion.close()
        trans.rollback()
        con.close()
        engine.dispose()


@pytest.fixture
def con_clerk(monkeypatch):
    monkeypatch.setattr(router, "get_settings", lambda: SimpleNamespace(clerk_configured=True))


def _cuenta(s: Session, tipo: str) -> CurrentUser:
    """Una cuenta de la empresa A con identidad de Clerk."""
    s.execute(text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA_A)})
    clerk_id = f"user_prueba_{uuid.uuid4().hex[:10]}"
    s.add(
        User(
            tenant_id=EMPRESA_A,
            clerk_id=clerk_id,
            email=f"{clerk_id}@prueba.cl",
            full_name=f"Cuenta {tipo}",
            user_type=tipo,
            status="active",
        )
    )
    s.flush()
    # **Se olvida la empresa**, que es como llega la sesion de `get_db` cuando no
    # la declaro antes la guarda de rutas. Sin esta linea la prueba declaraba por
    # su cuenta, y quitar `declarar` del predicado pasaba en verde.
    s.execute(text("SELECT set_config('ambienta.tenant_id', '', true)"))
    return CurrentUser(user_id=clerk_id, tenant_id=str(EMPRESA_A))


def _patch(s: Session, quien: CurrentUser, empresa: uuid.UUID, **campos) -> Tenant:
    return router.update_tenant(tenant_id=empresa, data=TenantUpdate(**campos), user=quien, db=s)


class TestLaCartera:
    def test_el_admin_global_ve_todas_las_empresas(self, s, con_clerk) -> None:
        ids = {t.id for t in router.list_tenants(user=_cuenta(s, "platform_admin"), db=s)}
        assert {EMPRESA_A, EMPRESA_B} <= ids

    def test_un_admin_empresa_sigue_viendo_solo_la_suya(self, s, con_clerk) -> None:
        ids = [t.id for t in router.list_tenants(user=_cuenta(s, "tenant_admin"), db=s)]
        assert ids == [EMPRESA_A]

    def test_sin_Clerk_nadie_ve_la_cartera(self, s) -> None:
        """Sin identidad no hay Admin Global que comprobar: una cabecera no basta."""
        ids = [t.id for t in router.list_tenants(user=_cuenta(s, "platform_admin"), db=s)]
        assert ids == [EMPRESA_A]

    def test_el_detalle_de_otra_empresa(self, s, con_clerk) -> None:
        assert router.get_tenant(tenant_id=EMPRESA_B, user=_cuenta(s, "platform_admin"), db=s).id == EMPRESA_B
        with pytest.raises(HTTPException) as e:
            router.get_tenant(tenant_id=EMPRESA_B, user=_cuenta(s, "tenant_admin"), db=s)
        assert e.value.status_code == 404


class TestElAdminGlobalSobreOtraEmpresa:
    def test_suspende_y_fija_el_tope_sin_tocar_el_resto(self, s, con_clerk) -> None:
        global_ = _cuenta(s, "platform_admin")
        antes = dict(s.get(Tenant, EMPRESA_B).settings or {})

        r = _patch(s, global_, EMPRESA_B, status="suspended", settings={**antes, "limiteUsuarios": 7})

        assert r.status == "suspended"
        assert r.settings["limiteUsuarios"] == 7
        assert {k: v for k, v in r.settings.items() if k != "limiteUsuarios"} == {
            k: v for k, v in antes.items() if k != "limiteUsuarios"
        }

    def test_no_edita_su_contenido(self, s, con_clerk) -> None:
        with pytest.raises(HTTPException) as e:
            _patch(s, _cuenta(s, "platform_admin"), EMPRESA_B, legal_name="Otra razon social")
        assert e.value.status_code == 403
        assert e.value.detail["codigo"] == "plataforma_no_edita_contenido"

    def test_un_admin_empresa_no_alcanza_otra_empresa(self, s, con_clerk) -> None:
        with pytest.raises(HTTPException) as e:
            _patch(s, _cuenta(s, "tenant_admin"), EMPRESA_B, status="suspended")
        assert e.value.status_code == 404


class TestUnaEmpresaSobreSiMisma:
    def test_edita_su_contenido(self, s, con_clerk) -> None:
        r = _patch(s, _cuenta(s, "tenant_admin"), EMPRESA_A, trade_name="Nombre de fantasia")
        assert r.trade_name == "Nombre de fantasia"

    @pytest.mark.parametrize("campo", ["status", "rut_tax_id"])
    def test_no_se_cambia_lo_de_plataforma(self, s, con_clerk, campo: str) -> None:
        valor = "suspended" if campo == "status" else "76.999.999-9"
        with pytest.raises(HTTPException) as e:
            _patch(s, _cuenta(s, "tenant_admin"), EMPRESA_A, **{campo: valor})
        assert e.value.status_code == 403

    def test_no_se_sube_el_tope(self, s, con_clerk) -> None:
        guardados = dict(s.get(Tenant, EMPRESA_A).settings or {})
        with pytest.raises(HTTPException) as e:
            _patch(
                s,
                _cuenta(s, "tenant_admin"),
                EMPRESA_A,
                settings={**guardados, "limiteUsuarios": guardados.get("limiteUsuarios", 50) + 100},
            )
        assert e.value.status_code == 403

    def test_guardar_el_logo_reenviando_el_tope_de_siempre_SI_funciona(self, s, con_clerk) -> None:
        """El caso que una regla ingenua romperia: la pantalla manda `settings`
        completo, con el tope y los modulos que ya mostraba."""
        empresa = s.get(Tenant, EMPRESA_A)
        guardados = dict(empresa.settings or {})
        eco = {
            "limiteUsuarios": guardados.get("limiteUsuarios", 50),
            "modulosActivos": guardados.get("modulosActivos", []),
        }

        r = _patch(
            s,
            _cuenta(s, "tenant_admin"),
            EMPRESA_A,
            rut_tax_id=empresa.rut_tax_id,
            settings={**guardados, **eco, "logoUrl": "https://ejemplo.cl/logo.png"},
        )

        assert r.settings["logoUrl"] == "https://ejemplo.cl/logo.png"
        # El valor por defecto reenviado no se escribe como si fuera un contrato.
        for clave in ("limiteUsuarios", "modulosActivos"):
            assert (clave in r.settings) == (clave in guardados)
