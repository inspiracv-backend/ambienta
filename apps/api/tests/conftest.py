"""Utilidades para probar la autenticacion sin una cuenta de Clerk.

Se genera un par RSA propio y se sirve su parte publica como si fuera la JWKS
de Clerk. Eso permite firmar tokens validos, expirados o con claims faltantes
y verificar cada camino del modulo `auth` sin red y sin credenciales.
"""
from __future__ import annotations

import base64
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app import auth
from app.config import get_settings

TEST_KID = "ambienta-test-key"
TEST_ISSUER = "https://clerk.test.ambienta.cl"
TEST_JWKS_URL = "https://clerk.test.ambienta.cl/.well-known/jwks.json"
TENANT_ID = "a0000000-0000-0000-0000-000000000001"


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[str, dict]:
    """Devuelve (PEM privado, JWKS publica). Se genera una vez por sesion."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    numbers = key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": TEST_KID,
                "use": "sig",
                "alg": "RS256",
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }
    return pem, jwks


@pytest.fixture
def make_token(rsa_keypair):
    """Fabrica tokens firmados con la llave de prueba."""
    pem, _ = rsa_keypair

    def _make(
        *,
        sub: str | None = "user_2testclerkid",
        tenant_id: str | None = TENANT_ID,
        expires_in: int = 3600,
        issuer: str | None = TEST_ISSUER,
        key: str | None = None,
    ) -> str:
        now = int(time.time())
        claims: dict = {"iat": now, "nbf": now, "exp": now + expires_in}
        if sub is not None:
            claims["sub"] = sub
        if tenant_id is not None:
            claims["tenant_id"] = tenant_id
        if issuer is not None:
            claims["iss"] = issuer
        return jwt.encode(
            claims,
            key or pem,
            algorithm="RS256",
            headers={"kid": TEST_KID},
        )

    return _make


@pytest.fixture
def clerk_enabled(monkeypatch, rsa_keypair):
    """Activa Clerk y sirve la JWKS de prueba en vez de salir a la red."""
    _, jwks = rsa_keypair
    monkeypatch.setenv("CLERK_JWKS_URL", TEST_JWKS_URL)
    monkeypatch.setenv("CLERK_ISSUER", TEST_ISSUER)
    get_settings.cache_clear()
    auth.reset_jwks_cache()

    calls: list[str] = []

    class _Response:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return jwks

    def _fake_get(url: str, **_kwargs):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(auth.httpx, "get", _fake_get)
    yield calls

    get_settings.cache_clear()
    auth.reset_jwks_cache()


@pytest.fixture
def clerk_disabled(monkeypatch):
    """Modo desarrollo: sin Clerk, se acepta el header X-Tenant-Id."""
    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    monkeypatch.delenv("CLERK_ISSUER", raising=False)
    get_settings.cache_clear()
    auth.reset_jwks_cache()
    yield
    get_settings.cache_clear()
    auth.reset_jwks_cache()
