"""Dependencias compartidas de FastAPI."""
from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import CurrentUser, verify_token
from .config import get_settings
from .db import SessionLocal

_bearer = HTTPBearer(auto_error=False, description="JWT emitido por Clerk")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_tenant_id: str | None = Header(default=None),
) -> CurrentUser:
    """Resuelve quien hace el request. Dos caminos, uno solo activo a la vez.

    Con Clerk configurado se exige un JWT firmado y el header X-Tenant-Id se
    ignora por completo. Sin Clerk (desarrollo local) se acepta el header, que
    es lo que permite trabajar sin una cuenta del proveedor.

    El fallback es seguro porque lo gobierna `clerk_configured`, que se deriva
    de `CLERK_JWKS_URL`: en cualquier entorno con esa variable puesta no existe
    camino que acepte un tenant sin firmar. No es un flag que se pueda olvidar
    apagado — es la misma variable que hace falta para validar tokens.
    """
    settings = get_settings()

    if settings.clerk_configured:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falta el token de autenticacion.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return verify_token(credentials.credentials)

    # --- Fallback de desarrollo ---------------------------------------------
    # Sin Clerk, la identidad del usuario no se conoce: solo el tenant que el
    # cliente declara. `user_id` queda vacio a proposito, para que cualquier
    # codigo que dependa de saber quien es el usuario falle de forma visible
    # en vez de inventarse una identidad.
    if x_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Falta el header X-Tenant-Id. Sin Clerk configurado, la API "
                "necesita saber el tenant de la sesion."
            ),
        )

    try:
        tenant_uuid = UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header must be a valid UUID",
        ) from None

    return CurrentUser(user_id="", tenant_id=str(tenant_uuid))


def get_tenant_id(user: CurrentUser = Depends(get_current_user)) -> UUID:
    """El tenant de la sesion, ya verificado.

    Antes leia el header directo; ahora sale del JWT firmado. Los 93 endpoints
    que dependen de esta funcion no cambiaron: solo cambio de donde viene el
    dato, no su forma.
    """
    try:
        return UUID(user.tenant_id)
    except ValueError:
        # Clerk firmo un tenant_id que no es UUID. Es un error de datos en
        # publicMetadata, no del cliente — pero no hay nada que la API pueda
        # hacer con el, asi que se rechaza el request.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El tenant de la sesion no es valido.",
        ) from None


def get_tenant_db(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> Generator[Session, None, None]:
    """Sesion de BD con el tenant declarado para que RLS filtre.

    No cambia con Clerk. Es deliberado: la capa que aplica Row Level Security
    no tiene por que saber como se autentico el usuario. Recibe un UUID
    verificado y hace siempre lo mismo.
    """
    db.execute(text("SET LOCAL ROLE ambienta_app"))
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    yield db
