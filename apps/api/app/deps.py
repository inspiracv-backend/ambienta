"""Dependencias compartidas de FastAPI."""
from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .auth import CurrentUser, verify_token
from .config import get_settings
from .db import AdminSessionLocal, SessionLocal
from .models.organization import User
from .services.auditoria_automatica import CONTEXTO as CONTEXTO_DE_AUDITORIA
from .services.invitado import credencial_vigente
from .services.perfil_empresa import estado as estado_del_perfil
from .services.token_invitado import SesionDeInvitado
from .services.token_invitado import verificar as verificar_token_de_invitado

_bearer = HTTPBearer(auto_error=False, description="JWT emitido por Clerk")


def get_db() -> Generator[Session, None, None]:
    """Sesion con el rol de la aplicacion, sin tenant declarado.

    Row Level Security **si** se aplica: el rol no puede saltarsela. Sirve para
    el catalogo global y para `tenants`, que no llevan `tenant_id` y por eso no
    tienen policies. Si se usa sobre una tabla de empresa devuelve cero filas —
    falla cerrado, no abierto.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_admin_db() -> Generator[Session, None, None]:
    """Sesion que **cruza empresas**. Usar solo donde ese es el proposito.

    Corre con el dueno de la base, que salta RLS. Hoy la usan dos cosas:

    - El webhook de Clerk. Un `user.deleted` trae solo el id, sin metadatos, asi
      que no hay forma de saber a que empresa pertenece antes de buscarlo: hay
      que poder mirarlas todas.
    - El health check del esquema, que cuenta objetos de la base.

    Cualquier uso nuevo tiene que justificarse igual de explicito. Si lo que se
    necesita es leer datos de una empresa, la dependencia correcta es
    `get_tenant_db`.
    """
    db = AdminSessionLocal()
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


def _declarar(db: Session, tenant_id: UUID) -> None:
    """Deja la sesion corriendo como `ambienta_app` con el tenant declarado."""
    db.execute(text("SET LOCAL ROLE ambienta_app"))
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def get_tenant_db(
    request: Request,
    tenant_id: UUID = Depends(get_tenant_id),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Generator[Session, None, None]:
    """Sesion de BD con el tenant declarado para que RLS filtre.

    No cambia con Clerk. Es deliberado: la capa que aplica Row Level Security
    no tiene por que saber como se autentico el usuario. Recibe un UUID
    verificado y hace siempre lo mismo.

    Ademas **deja en la sesion quien hace el request**, que es lo que permite
    que el registro de actividades se escriba solo. Va aca y no en un
    middleware porque aca ya esta resuelta la identidad y esta la sesion: son
    las dos mitades que el registro necesita, y separarlas obligaria a pasarlas
    por una variable global de contexto.

    Que viva en `db.info` y no en un `contextvar` no es un detalle de estilo:
    el contexto muere con la sesion, asi que **una sesion no puede heredar el
    actor de otro request**.
    """
    _declarar(db, tenant_id)
    db.info[CONTEXTO_DE_AUDITORIA] = {
        "tenant_id": tenant_id,
        # El id de Clerk, no el nuestro. Traducirlo cuesta una consulta y solo
        # se paga cuando de verdad hay algo que registrar.
        "clerk_id": user.user_id or None,
        "ip": request.client.host if request.client else None,
        "ruta": f"{request.method} {request.url.path}",
    }
    try:
        yield db
    finally:
        # La sesion vuelve al pool: el actor del request anterior no puede
        # quedar pegado al siguiente.
        db.info.pop(CONTEXTO_DE_AUDITORIA, None)


def sesion_publica_de_empresa(
    empresa_id: UUID,
    db: Session = Depends(get_db),
) -> Generator[Session, None, None]:
    """Sesion para el link publico del invitado. **Sin token, a proposito.**

    Es el unico lugar de la API donde el tenant lo declara quien llama sin haber
    probado nada, asi que conviene ser explicito sobre que protege y que no.

    **Lo que protege:** RLS sigue activa y el rol sigue siendo `ambienta_app`.
    Quien pida esta ruta con el UUID de una empresa ve —y escribe— solo lo de
    esa empresa. No hay forma de leer otra ni de saltar la barrera.

    **Lo que NO protege:** el UUID de la empresa no es una contrasena. Quien lo
    tenga puede pedir credenciales de invitado de esa empresa. Eso es lo que
    significa *link publico*, y es lo que el analisis pidio en RF-02: una
    persona sin cuenta tiene que poder abrir una solicitud. El UUID es v4, asi
    que adivinarlo no es un camino; compartirlo si.

    **Lo que falta:** un limite de peticiones. Sin el, este endpoint es una
    fabrica de credenciales para quien tenga el enlace. Ninguna de ellas abre
    nada de negocio —esa es la contencion real— pero la tabla crece. Queda
    anotado en `tasks.md` y no se resuelve en este archivo.

    Se usa **solo** en el router de acceso de invitado. Cualquier otro uso hay
    que justificarlo igual de explicito que `get_admin_db`.
    """
    _declarar(db, empresa_id)
    yield db


def get_invitado_actual(
    empresa_id: UUID,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Generator[tuple[SesionDeInvitado, Session], None, None]:
    """Quien es el invitado que llama, con su sesion de BD ya acotada.

    **Devuelve una tupla y no solo la identidad** porque las dos cosas tienen
    que salir del mismo sitio: la sesion se declara con el tenant que dice el
    token, no con uno que el endpoint elija despues. Separarlas dejaria la
    puerta a un endpoint que valida un token de la empresa A y consulta con la
    sesion de la B.

    Dos comprobaciones, y las dos hacen falta:

    1. **La firma**, que dice que el token lo emitimos nosotros y no caduco.
    2. **La credencial contra la base**, que dice que sigue viva. Un token vale
       30 dias; sin este paso, revocar una credencial filtrada no haria nada
       durante un mes.

    El `empresa_id` del path tiene que coincidir con el del token. Si no,
    alguien esta usando una sesion valida contra otra empresa.
    """
    sesion = verificar_token_de_invitado(
        credentials.credentials if credentials else ""
    )
    if sesion is None or sesion.tenant_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion de invitado invalida o vencida.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _declarar(db, sesion.tenant_id)

    if credencial_vigente(db, sesion.tenant_id, sesion.credencial_id) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion de invitado invalida o vencida.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    yield sesion, db


def exigir_perfil_de_empresa_completo(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
) -> None:
    """RF-10: no se opera Matriz Legal ni Obligaciones sin el perfil completo.

    Hasta hoy esto solo existia como una **redireccion del navegador**: con
    `curl` la API respondia igual con el perfil vacio. Un flujo obligatorio que
    solo se aplica en el cliente no es obligatorio.

    ## Tres acotaciones deliberadas, y cada una puede dejar gente fuera

    **Solo `admin_empresa`.** Es el texto literal de RF-10 —"primer paso del
    Admin Empresa"—. Un Encargado sigue trabajando aunque el perfil este a
    medias: bloquearlo seria castigarlo por algo que **no puede arreglar**, ya
    que completar el perfil no esta entre sus permisos.

    **Solo lectura no se bloquea.** `GET` pasa siempre. Impedir mirar no acerca
    a nadie a completar el perfil, y deja a la persona sin contexto para saber
    que le falta.

    **Sin Clerk no se aplica.** En desarrollo la sesion no identifica a nadie,
    asi que no se puede saber si quien llama es Admin Empresa. Bloquear a todos
    haria imposible trabajar en local; no bloquear a nadie es lo mismo que hoy.
    Queda dicho porque es la clase de guarda que **en local anda perfecto y en
    produccion no deja pasar a nadie**.

    Responde **409 y no 403**: no es falta de permiso, es un paso previo sin
    hacer. Un 403 mandaria a la persona a pedirle permisos a alguien.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    settings = get_settings()
    if not settings.clerk_configured:
        return

    quien = db.scalar(select(User).where(User.clerk_id == user.user_id))
    if quien is None or quien.user_type != "tenant_admin":
        return

    resultado = estado_del_perfil(db, tenant_id)
    if not resultado.completo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "mensaje": (
                    "Completa el Perfil Empresa antes de operar la Matriz Legal "
                    "o las Obligaciones."
                ),
                "faltantes": resultado.faltantes,
            },
        )


def exigir_admin_global(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> CurrentUser:
    """Solo el Admin Global administra empresas.

    Crear una empresa no pertenece a ninguna empresa, asi que no lo puede
    proteger `get_tenant_db`: no hay tenant contra el cual filtrar. Es la razon
    por la que el router de tenants quedo sin ninguna verificacion y cualquiera
    podia listar la cartera de clientes y crear empresas.

    El rol no viaja en el JWT —solo `sub` y `tenant_id`—, asi que se resuelve
    contra la base por `clerk_id`. Es una consulta extra por request, aceptable
    porque estos endpoints son de administracion, no del camino caliente.

    Sin Clerk configurado no hay identidad que consultar: el fallback de
    desarrollo ya confia enteramente en quien llama, asi que exigir aca un rol
    que no puede probar solo haria imposible trabajar en local. La barrera vive
    donde importa, que es cualquier entorno con Clerk puesto.

    Provisional: cuando entre `sistema-actores-roles-rbac` esto se reemplaza
    por la verificacion de permisos general.
    """
    if not get_settings().clerk_configured:
        return user

    fila = db.scalar(select(User).where(User.clerk_id == user.user_id))
    if fila is None or fila.user_type != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el Admin Global puede administrar empresas.",
        )
    return user


CODIGO_SIN_PERMISO = "permiso_insuficiente"


def exigir_permiso(codigo: str):
    """Guarda de permiso para un endpoint (RF-08).

    Se usa como `Depends(exigir_permiso("obligation.write"))`. Devuelve una
    dependencia y no un booleano porque FastAPI necesita resolverla por
    request, con su propia sesion.

    **El codigo tiene que existir en la tabla `permissions`.** Uno inventado no
    falla al escribirlo —es una cadena cualquiera— sino al usarlo, y en modo
    desarrollo ni siquiera ahi, porque esta guarda no verifica sin Clerk. Da un
    endpoint que en local anda perfecto y en produccion no puede llamar nadie.
    Lo comprueba `test_permisos.py::TestCodigosUsadosEnLaApi`, que tambien lee
    los ejemplos de estos docstrings: por eso el de arriba es un codigo real.

    ## Por que el 403 dice cual permiso falta

    Un 403 mudo obliga a adivinar. Devolver el codigo no filtra nada util a un
    atacante —ya sabe que ruta llamo— y le ahorra media hora a quien configura
    los roles de una empresa.

    ## Sin Clerk configurado no verifica

    Igual que `exigir_admin_global`: el modo de desarrollo confia enteramente
    en quien llama, asi que exigir aca un permiso que nadie puede probar solo
    haria imposible trabajar en local. La barrera vive donde importa.

    ## Esto no reemplaza a RLS

    Decide **si la operacion se permite**, no **que filas se ven**. El
    aislamiento entre empresas lo sigue garantizando Row Level Security, que es
    la unica barrera (CLAUDE.md §4). Un permiso concedido no deja ver datos de
    otra empresa: la consulta simplemente devuelve cero filas.
    """

    def verificar(
        user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_tenant_db),
    ) -> CurrentUser:
        if not get_settings().clerk_configured:
            return user

        from .services.permisos import tiene_permiso

        fila = db.scalar(select(User).where(User.clerk_id == user.user_id))
        if fila is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "codigo": CODIGO_SIN_PERMISO,
                    "mensaje": "Tu usuario no esta registrado en esta empresa.",
                    "permiso": codigo,
                },
            )
        if not tiene_permiso(db, fila.id, codigo):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "codigo": CODIGO_SIN_PERMISO,
                    "mensaje": "No tenes permiso para esta accion.",
                    "permiso": codigo,
                },
            )
        return user

    return verificar


def exigir_permiso_de_la_ruta(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> CurrentUser:
    """Guarda de permisos derivada de la ruta, para todos los endpoints.

    Se aplica una sola vez —como dependencia de la aplicacion— en vez de
    escribirse en cada endpoint. Son mas de 150 escrituras: ponerlo a mano es
    una decision que se puede olvidar, y **olvidarla no falla**, deja el
    endpoint abierto y nadie se entera.

    Que permiso exige cada ruta lo decide `permisos_de_rutas.py`, y
    `test_permisos_de_rutas.py` falla si aparece una raiz sin declarar.

    ## Sin Clerk configurado no verifica

    Igual que las otras guardas: el modo de desarrollo confia enteramente en
    quien llama, asi que exigir aca un permiso que nadie puede probar solo
    haria imposible trabajar en local.

    ## Esto no reemplaza a RLS

    Decide **si la operacion se permite**, no **que filas se ven**. El
    aislamiento entre empresas lo sigue garantizando Row Level Security, que es
    la unica barrera (CLAUDE.md §4).
    """
    if not get_settings().clerk_configured:
        return user

    from .permisos_de_rutas import permiso_requerido

    ruta = request.scope.get("route")
    camino = getattr(ruta, "path", None) or request.url.path
    codigo = permiso_requerido(camino, request.method)
    if codigo is None:
        return user

    from .services.permisos import tiene_permiso

    fila = db.scalar(select(User).where(User.clerk_id == user.user_id))
    if fila is None or not tiene_permiso(db, fila.id, codigo):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "codigo": CODIGO_SIN_PERMISO,
                "mensaje": "No tenes permiso para esta accion.",
                "permiso": codigo,
            },
        )
    return user
