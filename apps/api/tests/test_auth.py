"""Casos de validacion del JWT de Clerk.

Cubre la lista de verificacion de la Fase 1 de
`openspec/changes/integracion-clerk-auth/tasks.md`.
"""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app import auth
from app.deps import get_current_user, get_tenant_id

from .conftest import TENANT_ID


def _other_key_pem() -> str:
    """Una llave que la JWKS de prueba no conoce."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


# --- Token valido ------------------------------------------------------------


def test_token_valido_devuelve_identidad(clerk_enabled, make_token):
    user = auth.verify_token(make_token())

    assert user.user_id == "user_2testclerkid"
    assert user.tenant_id == TENANT_ID


def test_tenant_id_sale_del_token_no_del_header(clerk_enabled, make_token):
    """El header X-Tenant-Id se ignora cuando Clerk esta activo.

    Es la razon de ser de todo el cambio: sin esto, cualquiera podia leer datos
    de otro tenant fabricando un header.
    """
    otro_tenant = "b0000000-0000-0000-0000-000000000009"
    credentials = _bearer(make_token())

    user = get_current_user(credentials=credentials, x_tenant_id=otro_tenant)

    assert user.tenant_id == TENANT_ID
    assert user.tenant_id != otro_tenant


# --- Tokens rechazados -------------------------------------------------------


def test_token_expirado_da_401(clerk_enabled, make_token):
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(make_token(expires_in=-60))

    assert exc.value.status_code == 401


def test_token_sin_tenant_id_da_403_no_401(clerk_enabled, make_token):
    """Identidad verificada, sin empresa: **no** es un problema de sesion.

    Antes daba 401, que le decia al frontend "volve a entrar" sobre una sesion
    que estaba perfectamente bien. Con SSO abierto este caso es normal: alguien
    se autentica con Google sin estar dado de alta.
    """
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(make_token(tenant_id=None))

    assert exc.value.status_code == 403


def test_el_403_sin_empresa_trae_un_codigo_no_solo_texto(clerk_enabled, make_token):
    """El frontend ramifica sobre el codigo; el mensaje es para personas.

    Si esto fuera solo texto, la pantalla que explica el caso se romperia la
    primera vez que alguien mejore la redaccion.
    """
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(make_token(tenant_id=None))

    assert exc.value.detail["codigo"] == auth.CODIGO_SIN_EMPRESA
    assert exc.value.detail["mensaje"]


def test_sin_empresa_no_manda_a_reautenticar(clerk_enabled, make_token):
    """Un 401 lleva `WWW-Authenticate`, que invita a reintentar la credencial.

    Acá la credencial es correcta, así que esa cabecera seria una instruccion
    equivocada: reintentar no va a conseguir la empresa que falta.
    """
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(make_token(tenant_id=None))

    assert not (exc.value.headers or {}).get("WWW-Authenticate")


def test_token_sin_sub_da_401(clerk_enabled, make_token):
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(make_token(sub=None))

    assert exc.value.status_code == 401


def test_token_firmado_con_otra_llave_da_401(clerk_enabled, make_token):
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(make_token(key=_other_key_pem()))

    assert exc.value.status_code == 401


def test_token_de_otro_emisor_da_401(clerk_enabled, make_token):
    """Un JWT de otra instancia de Clerk no sirve contra esta API."""
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(make_token(issuer="https://clerk.otra-app.com"))

    assert exc.value.status_code == 401


def test_texto_cualquiera_da_401(clerk_enabled):
    with pytest.raises(HTTPException) as exc:
        auth.verify_token("no-soy-un-jwt")

    assert exc.value.status_code == 401


# --- Ausencia de token -------------------------------------------------------


def test_sin_token_con_clerk_activo_da_401(clerk_enabled):
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=None, x_tenant_id=TENANT_ID)

    assert exc.value.status_code == 401


def test_sin_token_sin_clerk_usa_el_header(clerk_disabled):
    """Modo desarrollo: el DevRoleSwitcher sigue funcionando."""
    user = get_current_user(credentials=None, x_tenant_id=TENANT_ID)

    assert user.tenant_id == TENANT_ID
    # Sin Clerk no se conoce la identidad: queda vacia a proposito, para que
    # nada asuma un usuario que no existe.
    assert user.user_id == ""


def test_sin_token_sin_clerk_y_sin_header_da_401(clerk_disabled):
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=None, x_tenant_id=None)

    assert exc.value.status_code == 401


def test_header_no_uuid_da_400(clerk_disabled):
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=None, x_tenant_id="no-es-uuid")

    assert exc.value.status_code == 400


# --- Cache de la JWKS --------------------------------------------------------


def test_la_jwks_se_descarga_una_sola_vez(clerk_enabled, make_token):
    """Sin cache serian dos llamadas HTTP por cada par de requests."""
    auth.verify_token(make_token())
    auth.verify_token(make_token())

    assert len(clerk_enabled) == 1


def test_sin_jwks_ni_cache_da_503_no_401(clerk_enabled, monkeypatch, make_token):
    """503 y no 401: el token puede estar bien; es la API la que no puede leerlo.

    Con 401 se mandaria a re-loguearse a usuarios cuyo token es valido, y el
    re-login tampoco funcionaria porque el problema no es la sesion.
    """
    import httpx

    auth.reset_jwks_cache()

    def _falla(url: str, **_kwargs):
        raise httpx.ConnectError("clerk no responde")

    monkeypatch.setattr(auth.httpx, "get", _falla)

    with pytest.raises(HTTPException) as exc:
        auth.verify_token(make_token())

    assert exc.value.status_code == 503


def test_si_clerk_cae_se_usa_el_cache_vencido(clerk_enabled, monkeypatch, make_token):
    """Una llave de hace dos horas verifica firmas igual de bien."""
    import httpx

    auth.verify_token(make_token())  # llena el cache

    monkeypatch.setattr(auth._jwks_cache, "_fetched_at", 0.0)  # lo vence

    def _falla(url: str, **_kwargs):
        raise httpx.ConnectError("clerk no responde")

    monkeypatch.setattr(auth.httpx, "get", _falla)

    user = auth.verify_token(make_token())

    assert user.tenant_id == TENANT_ID


# --- get_tenant_id -----------------------------------------------------------


def test_get_tenant_id_devuelve_uuid(clerk_enabled, make_token):
    from uuid import UUID

    user = auth.verify_token(make_token())

    assert get_tenant_id(user=user) == UUID(TENANT_ID)


def test_get_tenant_id_con_tenant_no_uuid_da_401(clerk_enabled, make_token):
    user = auth.verify_token(make_token(tenant_id="no-es-uuid"))

    with pytest.raises(HTTPException) as exc:
        get_tenant_id(user=user)

    assert exc.value.status_code == 401


# --- helpers -----------------------------------------------------------------


def _bearer(token: str):
    from fastapi.security import HTTPAuthorizationCredentials

    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
