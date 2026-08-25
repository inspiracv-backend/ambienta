"""Quien esta llamando: identidad, empresa, permisos y alcance.

## Por que hace falta un endpoint para esto

El JWT trae solo dos claims: `sub` —el id de Clerk— y `tenant_id`. Con eso la
API sabe **contra que empresa** consultar, pero quien llama no sabe nada de si
mismo: ni su nombre, ni su rol, ni que puede hacer, ni a que instalaciones esta
acotado.

Para una interfaz eso se resolvia leyendo `/users/` y buscando la fila propia.
Para un servicio que consume la API —el asistente de IA, por ejemplo— eso es
peor que incomodo: **tendria que traerse la nomina completa de la empresa para
averiguar quien es**, y ademas necesita su UUID interno, que el JWT no lleva.

Este endpoint responde esa pregunta en una sola llamada, y es el primer paso
natural de cualquier integracion: **antes de contestar nada sobre una empresa
hay que saber de que empresa se esta hablando.**

## No expone nada que quien llama no pudiera ver

Devuelve la fila del propio usuario y la de su empresa, resueltas por RLS. Los
permisos que informa son los que la API ya aplica en cada request: decirlos no
concede nada, evita que el cliente los adivine y muestre acciones que despues
van a fallar con 403.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..config import get_settings
from ..deps import get_current_user, get_tenant_db
from ..models.catalog import Sector
from ..models.organization import Tenant, User
from ..schemas.identidad import (
    EmpresaDeLaSesion,
    IdentidadRead,
    SectorDeLaEmpresa,
    UsuarioDeLaSesion,
    PerfilDeLaEmpresa,
)
from ..services.perfil_empresa import estado as estado_del_perfil
from ..services.clave_local import (
    LARGO_MINIMO_DE_CLAVE,
    ClerkNoDisponible,
    ErrorDeClaveLocal,
    RutOcupado,
    fijar,
)
from ..services.permisos import (
    alcance_del_usuario,
    permisos_efectivos,
    roles_vigentes,
)

router = APIRouter(prefix="/me", tags=["identidad"])

#: Codigo de error cuando el token es valido pero no hay fila que le corresponda.
CODIGO_SIN_USUARIO = "sesion_sin_usuario"


def _perfil(db: Session, tenant_id: UUID | str) -> PerfilDeLaEmpresa:
    """El estado del Perfil Empresa, calculado contra la base.

    Se expone en `/me` porque es donde la pantalla ya pregunta "quien soy y que
    puedo hacer": pedirlo aparte obligaria a una segunda llamada en cada carga
    para algo que se necesita siempre.
    """
    # `UUID | str` y no `UUID` a secas: `CurrentUser.tenant_id` es texto cuando
    # viene del JWT y ya es un `UUID` en las pruebas que llaman a esta funcion
    # sin pasar por HTTP. El driver adapta las dos; convertir a la fuerza
    # reventaba con `'UUID' object has no attribute 'replace'`.
    resultado = estado_del_perfil(db, tenant_id)
    return PerfilDeLaEmpresa(
        completo=resultado.completo,
        faltantes=resultado.faltantes,
        tiene_giro=resultado.tiene_giro,
        tiene_instalaciones=resultado.tiene_instalaciones,
        tiene_departamentos=resultado.tiene_departamentos,
        tiene_sector=resultado.tiene_sector,
    )


@router.get("", response_model=IdentidadRead)
def quien_soy(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """Quien esta llamando, de que empresa, y que puede hacer.

    **Es la primera llamada de cualquier integracion.** El token dice contra que
    empresa consultar, pero no dice quien es quien llama: sin esto, un servicio
    tendria que traerse la nomina entera para encontrar su propia fila, y
    seguiria sin conocer su UUID interno —el que usan el resto de los
    endpoints—, porque el JWT lleva el id de Clerk, que es otro.

    ## Que devuelve

    - **`usuario`**: la fila propia, con su UUID interno, nombre, correo y tipo.
    - **`empresa`**: la empresa del token, con su **sector economico y tramo por
      tamano**, que son los que determinan que normativa le aplica.
    - **`permisos`**: lo que esta persona puede hacer, ya resuelto — roles mas
      concesiones individuales, menos las denegaciones. **La denegacion gana.**
    - **`instalaciones` y `departamentos`**: a que esta acotada, si lo esta.

    ## Un alcance vacio significa "sin acotar", no "ninguno"

    Es la diferencia entre un encargado de toda la empresa y uno que no tiene
    acceso a nada, y confundirlas deja a los administradores viendo una pantalla
    en blanco. El campo `acotado` lo dice explicito para que nadie tenga que
    interpretar una lista vacia.

    ## Sin Clerk configurado

    En desarrollo la API acepta el header `X-Tenant-Id` y no hay identidad que
    resolver. Este endpoint devuelve la empresa y **`usuario` en `null`**, con
    `permisos` vacio y `modo_desarrollo` en `true`. No inventa un usuario: un
    cliente que reciba una identidad falsa la va a mostrar como verdadera.
    """
    empresa = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    if empresa is None:
        # RLS no encontro la empresa del token. Pasa si el `tenant_id` del JWT
        # apunta a una empresa borrada o inexistente.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "codigo": CODIGO_SIN_USUARIO,
                "mensaje": "El token apunta a una empresa que no existe.",
            },
        )

    # El sector se resuelve entero —codigo y nombre— y no solo el id: el id es
    # una clave interna que no explica nada, y quien consuma esto necesita poder
    # decir "le aplica porque es industria manufacturera", no "porque es 3".
    sector = None
    if empresa.sector_id is not None:
        fila_sector = db.execute(
            select(Sector.id, Sector.code, Sector.name).where(
                Sector.id == empresa.sector_id
            )
        ).first()
        if fila_sector is not None:
            sector = SectorDeLaEmpresa(
                id=fila_sector[0], codigo=fila_sector[1], nombre=fila_sector[2]
            )

    datos_empresa = EmpresaDeLaSesion(
        id=empresa.id,
        nombre=empresa.legal_name,
        nombre_comercial=empresa.trade_name,
        rut=empresa.rut_tax_id,
        tipo=empresa.tenant_type,
        sector=sector,
        sector_id=empresa.sector_id,
        tramo=empresa.size_bracket,
        giro=empresa.business_activity,
    )

    if not get_settings().clerk_configured:
        return IdentidadRead(
            modo_desarrollo=True,
            perfil_empresa=_perfil(db, user.tenant_id),
            usuario=None,
            empresa=datos_empresa,
            roles=[],
            permisos=[],
            acotado=False,
            instalaciones=[],
            departamentos=[],
        )

    fila = db.scalar(select(User).where(User.clerk_id == user.user_id))
    if fila is None:
        # El token es valido y la empresa existe, pero nadie registro a esta
        # persona. Es el estado que deja el SSO cuando el webhook no corrio, y
        # se explica asi en vez de con un 404 generico: la causa es operativa,
        # no un error de quien llama.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "codigo": CODIGO_SIN_USUARIO,
                "mensaje": "Tu cuenta existe en el proveedor de identidad pero "
                "no esta registrada en esta empresa.",
            },
        )

    instalaciones, departamentos = alcance_del_usuario(db, fila.id)
    roles = roles_vigentes(db, fila.id)

    return IdentidadRead(
        modo_desarrollo=False,
        perfil_empresa=_perfil(db, user.tenant_id),
        usuario=UsuarioDeLaSesion(
            id=fila.id,
            clerk_id=fila.clerk_id,
            email=fila.email,
            nombre=fila.full_name,
            tipo=fila.user_type,
            estado=fila.status,
            department_id=fila.department_id,
        ),
        empresa=datos_empresa,
        roles=roles,
        permisos=sorted(permisos_efectivos(db, fila.id)),
        # Se dice explicito en vez de dejar que el cliente interprete la lista
        # vacia, que significa lo contrario de lo que parece.
        acotado=bool(instalaciones or departamentos),
        instalaciones=sorted(instalaciones, key=str),
        departamentos=sorted(departamentos, key=str),
    )


class ClaveLocalPeticion(BaseModel):
    """Lo que la persona escribe en su perfil para fijar la clave local."""

    rut: str = Field(
        description="Con puntos, sin puntos o sin guion: se normaliza acá.",
        examples=["12.345.678-5"],
    )
    clave: str = Field(
        min_length=LARGO_MINIMO_DE_CLAVE,
        description=(
            "**Clerk aplica además su propia política**, incluida la lista de "
            "contraseñas filtradas, así que puede rechazar una que acá pase. Su "
            "mensaje se devuelve tal cual porque explica mejor que uno nuestro."
        ),
    )


class ClaveLocalRespuesta(BaseModel):
    rut: str
    mensaje: str


@router.post(
    "/clave-local",
    response_model=ClaveLocalRespuesta,
    summary="Fijar RUT y clave local para ingresar sin el proveedor externo",
    description=(
        "Quien entró con un proveedor externo fija su RUT y una clave, y desde "
        "entonces puede ingresar con ellos (RF-06).\n\n"
        "**No reemplaza el acceso anterior, lo suma:** el ingreso por el "
        "proveedor sigue funcionando igual.\n\n"
        "La clave la guarda el proveedor de identidad, no esta API. Tener dos "
        "almacenes de contraseñas serían dos políticas de robustez y dos "
        "lugares donde revocar una sesión."
    ),
    responses={
        409: {"description": "Ese RUT ya está registrado. **No se dice de quién**."},
        422: {"description": "RUT inválido o clave que el proveedor rechaza."},
        503: {"description": "Falta la clave secreta del proveedor, o no responde."},
    },
)
def fijar_clave_local(
    datos: ClaveLocalPeticion,
    usuario: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> ClaveLocalRespuesta:
    """Fija la credencial local de **quien hace el request**, nadie más.

    El usuario sale de la sesión y no del cuerpo: si viniera del cuerpo,
    cualquiera podría fijarle una clave a otra persona y entrar con ella.
    """
    fila = db.scalar(select(User).where(User.clerk_id == usuario.user_id))
    if fila is None:
        # Entró por SSO y el webhook no alcanzó a crear su fila — en local no
        # llega nunca. Sin fila no hay dónde guardar el RUT (D5).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Tu cuenta todavía no está sincronizada con esta empresa. "
                "Vuelve a intentarlo en unos minutos."
            ),
        )

    try:
        fijada = fijar(
            db,
            user_id=fila.id,
            clerk_id=usuario.user_id,
            rut=datos.rut,
            clave=datos.clave,
        )
    except RutOcupado as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ErrorDeClaveLocal as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except ClerkNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    db.commit()
    return ClaveLocalRespuesta(
        rut=fijada.rut,
        mensaje="Listo: ya puedes ingresar con tu RUT y tu clave.",
    )
