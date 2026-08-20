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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..config import get_settings
from ..deps import get_current_user, get_tenant_db
from ..models.organization import Tenant, User
from ..schemas.identidad import EmpresaDeLaSesion, IdentidadRead, UsuarioDeLaSesion
from ..services.permisos import alcance_del_usuario, permisos_efectivos

router = APIRouter(prefix="/me", tags=["identidad"])

#: Codigo de error cuando el token es valido pero no hay fila que le corresponda.
CODIGO_SIN_USUARIO = "sesion_sin_usuario"


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

    datos_empresa = EmpresaDeLaSesion(
        id=empresa.id,
        nombre=empresa.legal_name,
        nombre_comercial=empresa.trade_name,
        rut=empresa.rut_tax_id,
        sector_id=empresa.sector_id,
        tramo=empresa.size_bracket,
        giro=empresa.business_activity,
    )

    if not get_settings().clerk_configured:
        return IdentidadRead(
            modo_desarrollo=True,
            usuario=None,
            empresa=datos_empresa,
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

    return IdentidadRead(
        modo_desarrollo=False,
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
        permisos=sorted(permisos_efectivos(db, fila.id)),
        # Se dice explicito en vez de dejar que el cliente interprete la lista
        # vacia, que significa lo contrario de lo que parece.
        acotado=bool(instalaciones or departamentos),
        instalaciones=sorted(instalaciones, key=str),
        departamentos=sorted(departamentos, key=str),
    )
