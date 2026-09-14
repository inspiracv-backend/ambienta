"""La cartera de un Gestor y su forma de actuar por un cliente (#59, #60, #65).

Medido el 4-sep antes de escribir esto: el gestor del seed tiene un contrato con
su cliente y **al entrar ve un sistema vacio** — cero obligaciones, cero rutas
que nombren a un cliente. El modelo sabia quien administra a quien y no habia
ningun camino para actuar sobre ello.

Lo que se agrega es deliberadamente poco: **una lista y una cabecera**. Todo el
resto de la API ya funciona; lo que faltaba era poder declarar el otro tenant.
Ver `deps.tenant_efectivo` para por que esto no toca RLS.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import declarar, get_tenant_db, get_tenant_id
from ..schemas.gestor import ClienteDeLaCartera
from ..services import gestor as svc

router = APIRouter(prefix="/gestor", tags=["gestor"])


@router.get(
    "/clientes",
    response_model=list[ClienteDeLaCartera],
    summary="La cartera de clientes de este gestor",
    description=(
        "Las empresas con las que este gestor tiene contrato, **vigentes y no "
        "vigentes**.\n\n"
        "Los no vigentes no se filtran a proposito: un cliente cuyo contrato "
        "vencio tiene que verse en la cartera, con su motivo, en vez de "
        "desaparecer — desaparecer se leeria como que se perdio al cliente.\n\n"
        "`puede_actuar` dice si hoy se puede mandar `X-Cliente-Id` con ese "
        "identificador. Exige contrato **`active` y dentro de sus fechas**: el "
        "estado es una decision y la fecha es un hecho, y un contrato al que se "
        "le paso la fecha sin que nadie lo marcara sigue diciendo `active`."
    ),
)
def mi_cartera(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """**Usa `get_tenant_id` y no el efectivo**, a proposito.

    La cartera es del gestor. Si tomara el tenant efectivo, un gestor que esta
    actuando por un cliente pediria la cartera y recibiria la del cliente —
    vacia— y perderia la forma de volver.

    **Y no basta con el id: hay que redeclarar la sesion.** `get_tenant_db`
    declara el tenant *efectivo*, asi que mientras el gestor actua por un
    cliente la sesion tiene al cliente puesto y `contracts` —que lleva RLS—
    devuelve cero filas. Pasar el id correcto a una sesion declarada mal da una
    cartera vacia sin ningun error, que es la trampa de §4 otra vez.
    """
    declarar(db, tenant_id)

    if not svc.es_gestor(db, tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Esta empresa no es un gestor. La cartera de clientes existe "
                "solo para las empresas que administran a otras."
            ),
        )
    return svc.cartera(db, tenant_id)
