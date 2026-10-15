"""
Quién pregunta y de qué empresa (SPEC-02).

La empresa sale del claim `tenant_id` de un JWT de Clerk verificado, y de ningún otro lado.
Con Clerk configurado, `X-Tenant-Id` se ignora por completo; sin Clerk (modo desarrollo) es la
única forma de decir la empresa, y no hay usuario. Es la misma regla que aplica el backend, y
la gobierna la misma variable: `CLERK_JWKS_URL`.

El token de la persona se reenvía al backend. El AI Service no tiene credenciales propias para
leer datos de una empresa: si la persona no puede ver algo, el asistente tampoco.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import jwt

from .backend import ClienteBackend, SinAutenticar
from .backend import SinPermiso as SinPermisoBackend

PERMISO_CHATBOT = "chatbot.use"


class ErrorIdentidad(Exception):
    def __init__(self, estado: int, codigo: str, detalle: str):
        super().__init__(detalle)
        self.estado = estado
        self.codigo = codigo
        self.detalle = detalle


@dataclass(frozen=True)
class Sesion:
    tenant_id: UUID
    usuario_id: UUID | None
    permisos: frozenset[str]
    modo_desarrollo: bool
    token: str | None = field(default=None, repr=False)
    # Admin Global (usuario de tipo platform_admin): ve la cartera, no los datos de las empresas.
    es_plataforma: bool = False

    def puede(self, permiso: str) -> bool:
        """
        En modo desarrollo `/me` devuelve los permisos vacíos y el backend no los exige:
        se tratan como concedidos, igual que del otro lado.
        """
        return self.modo_desarrollo or permiso in self.permisos


class VerificadorClerk:
    """Valida la firma contra el JWKS de Clerk. Las claves se cachean."""

    def __init__(
        self,
        jwks_url: str,
        issuer: str | None = None,
        *,
        obtener_clave: Callable[[str], Any] | None = None,
    ):
        # Vacío = no validar el emisor, igual que el backend (`settings.clerk_issuer or None`).
        # Con CLERK_ISSUER="" en el entorno, pasar "" a jwt.decode exige un claim `iss` y
        # rechaza todos los tokens: encontrado el 21/09/2026 contra el backend real.
        self._issuer = issuer or None
        if obtener_clave is None:
            cliente_jwks = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)

            def obtener_clave(token: str) -> Any:
                return cliente_jwks.get_signing_key_from_jwt(token).key

        self._obtener_clave = obtener_clave

    async def verificar(self, token: str) -> dict[str, Any]:
        try:
            clave = await asyncio.to_thread(self._obtener_clave, token)
            return jwt.decode(
                token,
                clave,
                algorithms=["RS256", "ES256"],
                issuer=self._issuer,
                options={"require": ["exp", "sub"], "verify_aud": False},
            )
        except jwt.PyJWTError as e:
            raise ErrorIdentidad(401, "token_invalido", f"Token inválido: {e}") from e


FabricaCliente = Callable[..., ClienteBackend]


async def resolver_sesion(
    *,
    authorization: str | None,
    x_tenant_id: str | None,
    backend_url: str,
    verificador: VerificadorClerk | None,
    exigir_chatbot: bool = True,
    opciones_cliente: dict[str, Any] | None = None,
) -> tuple[Sesion, ClienteBackend]:
    """
    Devuelve la sesión y un cliente del backend ya atado a ella.

    `verificador is None` significa modo desarrollo.
    """
    opciones = opciones_cliente or {}

    if verificador is None:
        if not x_tenant_id:
            raise ErrorIdentidad(401, "sin_empresa", "Modo desarrollo: falta la cabecera X-Tenant-Id.")
        try:
            tenant = UUID(x_tenant_id)
        except ValueError as e:
            raise ErrorIdentidad(401, "sin_empresa", "X-Tenant-Id no es un UUID.") from e
        cliente = ClienteBackend.modo_desarrollo(backend_url, tenant, **opciones)
        sesion = Sesion(tenant_id=tenant, usuario_id=None, permisos=frozenset(), modo_desarrollo=True)
        return sesion, cliente

    token = _bearer(authorization)
    claims = await verificador.verificar(token)
    tenant_claim = claims.get("tenant_id")
    if not tenant_claim:
        raise ErrorIdentidad(403, "sin_empresa", "La cuenta no tiene empresa asignada (falta tenant_id).")
    try:
        tenant = UUID(str(tenant_claim))
    except ValueError as e:
        raise ErrorIdentidad(403, "sin_empresa", "El tenant_id del token no es un UUID.") from e

    cliente = ClienteBackend.con_token(backend_url, token, **opciones)
    try:
        me = await cliente.yo()
    except SinAutenticar as e:
        await cliente.cerrar()
        raise ErrorIdentidad(401, "token_invalido", e.detalle) from e
    except SinPermisoBackend as e:
        await cliente.cerrar()
        raise ErrorIdentidad(403, "sin_empresa", e.detalle) from e

    sesion = Sesion(
        tenant_id=tenant,
        usuario_id=me.usuario.id if me.usuario else None,
        permisos=frozenset(me.permisos),
        modo_desarrollo=False,
        token=token,
        es_plataforma=bool(me.usuario and me.usuario.tipo == "platform_admin"),
    )
    if exigir_chatbot and not sesion.puede(PERMISO_CHATBOT):
        await cliente.cerrar()
        raise ErrorIdentidad(403, "falta_permiso", f"Falta el permiso {PERMISO_CHATBOT}.")
    return sesion, cliente


def _bearer(authorization: str | None) -> str:
    if not authorization:
        raise ErrorIdentidad(401, "sin_token", "Falta el token.")
    esquema, _, token = authorization.partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        raise ErrorIdentidad(401, "sin_token", "Se esperaba Authorization: Bearer <token>.")
    return token.strip()
