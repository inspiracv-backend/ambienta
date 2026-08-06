"""Validacion del JWT de Clerk. La unica pieza de la API acoplada al proveedor.

Todo lo que sabe de Clerk vive aca. `deps.py` y los 12 routers solo ven
`CurrentUser`, que es nuestro. Cambiar de proveedor de identidad significa
reescribir este archivo y nada mas — es la mitigacion explicita del lock-in
que exige ADR-006.

Se valida la firma localmente contra la JWKS publica en vez de usar el SDK de
Clerk. El SDK hace una llamada HTTP a Clerk por cada request; verificar RS256
con una llave cacheada no depende de que Clerk este arriba ni agrega latencia
de red al camino caliente.

Spec: openspec/changes/integracion-clerk-auth/design.md §2.3.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError

from .config import get_settings

logger = logging.getLogger(__name__)

# La JWKS cambia solo cuando Clerk rota sus llaves (meses). Una hora de cache
# evita un round-trip HTTP por request sin arriesgar servir una llave retirada
# por mas de ese plazo.
_JWKS_TTL_SECONDS = 3600
_JWKS_TIMEOUT_SECONDS = 5.0

# `auto_error=False` es lo que permite el fallback de desarrollo: con el default
# (True) FastAPI responde 403 antes de que este modulo pueda decidir nada.
_bearer = HTTPBearer(auto_error=False, description="JWT emitido por Clerk")


@dataclass(frozen=True)
class CurrentUser:
    """Identidad ya verificada. Es lo unico que el resto de la API consume."""

    user_id: str
    """`sub` del JWT — el id de Clerk (`user_2abc...`), no nuestro UUID."""

    tenant_id: str
    """UUID del tenant, tomado del claim firmado. No se puede falsificar."""


class _JwksCache:
    """Cache en memoria con TTL.

    En memoria y no en Redis a proposito: Redis no esta en el stack y agregarlo
    por un documento que cambia cada varios meses no se justifica. Cada worker
    mantiene su copia; el costo es una descarga por worker por hora.
    """

    def __init__(self) -> None:
        self._keys: dict | None = None
        self._fetched_at: float = 0.0

    def get_cached(self) -> dict | None:
        if self._keys is None:
            return None
        if time.monotonic() - self._fetched_at > _JWKS_TTL_SECONDS:
            return None
        return self._keys

    def get_stale(self) -> dict | None:
        """La copia vencida, para sobrevivir a una caida momentanea de Clerk."""
        return self._keys

    def store(self, keys: dict) -> None:
        self._keys = keys
        self._fetched_at = time.monotonic()

    def clear(self) -> None:
        self._keys = None
        self._fetched_at = 0.0


_jwks_cache = _JwksCache()


def reset_jwks_cache() -> None:
    """Vacia el cache. Existe para los tests; no se llama en produccion."""
    _jwks_cache.clear()


def _fetch_jwks() -> dict:
    """Descarga la JWKS, con la copia vencida como red de seguridad.

    Si Clerk no responde y hay una copia vieja, se usa: una llave de hace dos
    horas sigue verificando firmas correctamente, y rechazar a todos los
    usuarios porque el CDN de Clerk parpadeo seria peor que el riesgo que
    cubre el TTL.
    """
    settings = get_settings()
    try:
        response = httpx.get(settings.clerk_jwks_url, timeout=_JWKS_TIMEOUT_SECONDS)
        response.raise_for_status()
        keys = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        stale = _jwks_cache.get_stale()
        if stale is not None:
            logger.warning(
                "No se pudo refrescar la JWKS de Clerk (%s). Se usa la copia "
                "en cache, vencida pero valida para verificar firmas.",
                exc,
            )
            return stale
        # Sin cache no hay forma de verificar nada. 503 y no 401: el usuario
        # puede estar perfectamente autenticado — es la API la que no puede
        # comprobarlo. Devolver 401 mandaria a re-loguearse a gente cuyo token
        # esta bien, y el re-login tampoco funcionaria.
        logger.error("JWKS de Clerk inaccesible y sin cache previo: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se puede verificar la identidad en este momento.",
        ) from exc

    _jwks_cache.store(keys)
    return keys


def get_jwks() -> dict:
    cached = _jwks_cache.get_cached()
    if cached is not None:
        return cached
    return _fetch_jwks()


def _decode(token: str, jwks: dict) -> dict:
    settings = get_settings()
    # `verify_aud=False` porque Clerk no emite `aud` por defecto en los tokens
    # de sesion. El emisor sí se valida cuando esta configurado, que es lo que
    # impide que un JWT de otra instancia de Clerk sirva contra esta API.
    options = {"verify_aud": False}
    issuer = settings.clerk_issuer or None
    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        options=options,
        issuer=issuer,
    )


def verify_token(token: str) -> CurrentUser:
    """Verifica un JWT de Clerk y devuelve la identidad. 401 si no es valido.

    Separada de `get_current_user` para poder testearla sin levantar FastAPI y
    para que `deps.py` la use sin arrastrar el objeto `Request`.
    """
    try:
        payload = _decode(token, get_jwks())
    except JWTError as exc:
        # Firma mala, token expirado, emisor distinto, algoritmo no permitido:
        # todos terminan aca. No se distingue el motivo hacia afuera para no
        # dar pistas a quien este probando tokens.
        logger.info("JWT de Clerk rechazado: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")

    if not user_id or not tenant_id:
        # El token esta firmado por Clerk pero no trae `tenant_id`. Casi
        # siempre significa que falta configurar el JWT Template que mapea
        # publicMetadata al claim (Fase 0 de tasks.md). Se registra como
        # warning porque es un error de configuracion, no un ataque.
        logger.warning(
            "JWT de Clerk sin claims requeridos (sub=%s, tenant_id=%s). "
            "Revisar el JWT Template en el dashboard de Clerk.",
            bool(user_id),
            bool(tenant_id),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no identifica usuario y empresa.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(user_id=str(user_id), tenant_id=str(tenant_id))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Dependencia de FastAPI: exige un Bearer token valido de Clerk."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticacion.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(credentials.credentials)
