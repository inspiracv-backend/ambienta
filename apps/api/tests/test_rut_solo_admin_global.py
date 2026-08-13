"""El RUT de una empresa solo lo cambia el Admin Global.

`rut_tax_id` se agrego a `TenantUpdate` el 13-ago-2026 porque sin el no habia
forma de completar el Perfil Empresa: la aplicacion lo considera completo cuando
hay giro **y** RUT, y la pantalla ofrecia marcar como completo algo que la API
no dejaba completar.

Abrirlo a secas habria sido peor que el problema. El RUT identifica legalmente a
la empresa ante la autoridad ambiental: si su propio administrador puede
cambiarlo, puede emitir declaraciones a nombre de otra. Por eso el campo existe
pero el router lo acota, y por eso estas pruebas existen.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import CurrentUser
from app.models.organization import User
from app.routers import tenants as router_tenants
from app.schemas.organization import TenantUpdate

TENANT = "a0000000-0000-0000-0000-000000000001"


class _SesionFalsa:
    """Sesion minima que responde distinto segun **que** se este consultando.

    En esta ruta hay dos consultas seguidas: la del usuario, para saber si es
    Admin Global, y la de la empresa. Un doble que devuelva lo mismo a las dos
    hace que la busqueda de la empresa reciba un usuario y el flujo siga como si
    la hubiera encontrado — que es como este archivo rompio CI la primera vez.
    """

    def __init__(self, usuario=None, empresa=None) -> None:
        self._usuario = usuario
        self._empresa = empresa
        self.escrituras = 0

    def scalar(self, stmt):
        entidad = stmt.column_descriptions[0]["entity"]
        return self._usuario if entidad is User else self._empresa

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.escrituras += 1


class _UsuarioFalso:
    def __init__(self, user_type: str) -> None:
        self.user_type = user_type


def _usuario_de_sesion() -> CurrentUser:
    return CurrentUser(user_id="user_2abc", tenant_id=TENANT)


@pytest.fixture
def con_clerk(monkeypatch):
    """El guard solo aplica con proveedor configurado."""
    from app.config import get_settings

    monkeypatch.setenv("CLERK_JWKS_URL", "https://ejemplo.test/jwks.json")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    get_settings.cache_clear()


def test_admin_empresa_no_puede_cambiar_el_rut(con_clerk):
    db = _SesionFalsa(_UsuarioFalso("tenant_admin"))

    with pytest.raises(HTTPException) as exc:
        router_tenants.update_tenant(
            tenant_id=TENANT,
            data=TenantUpdate(rut_tax_id="76.999.888-7"),
            user=_usuario_de_sesion(),
            db=db,
        )

    assert exc.value.status_code == 403
    # Y no se escribio nada: el rechazo va antes de tocar la fila.
    assert db.escrituras == 0


def test_el_admin_empresa_si_puede_editar_el_resto(con_clerk):
    """El guard es por campo, no por ruta.

    Si bloqueara el `PATCH` entero, una empresa no podria ni corregir su propio
    giro, que es justo lo que la pantalla de Perfil Empresa necesita.
    """
    db = _SesionFalsa(_UsuarioFalso("tenant_admin"))

    with pytest.raises(HTTPException) as exc:
        router_tenants.update_tenant(
            tenant_id=TENANT,
            data=TenantUpdate(business_activity="Mineria del cobre"),
            user=_usuario_de_sesion(),
            db=db,
        )

    # Llega hasta buscar la empresa (que esta sesion falsa no tiene), asi que
    # el guard del RUT lo dejo pasar. Lo que importa es que NO sea 403.
    assert exc.value.status_code == 404


def test_una_empresa_ajena_sigue_dando_404_no_403(con_clerk):
    """El 404 va primero: no se confirma que la empresa exista."""
    db = _SesionFalsa(_UsuarioFalso("platform_admin"))

    with pytest.raises(HTTPException) as exc:
        router_tenants.update_tenant(
            tenant_id="b0000000-0000-0000-0000-000000000002",
            data=TenantUpdate(rut_tax_id="76.999.888-7"),
            user=_usuario_de_sesion(),
            db=db,
        )

    assert exc.value.status_code == 404


def test_sin_proveedor_configurado_no_se_bloquea():
    """Modo desarrollo: no hay identidad que consultar.

    El fallback ya confia enteramente en quien llama, asi que exigir aca un rol
    que no puede probar solo haria imposible trabajar en local.
    """
    db = _SesionFalsa(None)

    with pytest.raises(HTTPException) as exc:
        router_tenants.update_tenant(
            tenant_id=TENANT,
            data=TenantUpdate(rut_tax_id="76.999.888-7"),
            user=_usuario_de_sesion(),
            db=db,
        )

    assert exc.value.status_code == 404  # llego a buscar la fila, no fue 403


def test_el_rut_esta_en_el_contrato():
    """Si desaparece del esquema, el Perfil Empresa vuelve a ser incompletable."""
    assert "rut_tax_id" in TenantUpdate.model_fields
