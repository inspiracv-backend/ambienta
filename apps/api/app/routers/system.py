from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alcance import instalaciones_permitidas
from ..deps import get_tenant_db, get_tenant_id
from ..models.organization import User
from ..services.husos import huso_de
from ..models.system import AuditLog
from ._paginacion import Pagina, paginacion, recortar
from ..schemas.system import AuditLogRead

router = APIRouter(prefix="/system", tags=["system"])

#: Codigo del 403 de alcance, distinto del de permiso: no le falta un permiso
#: que alguien pueda concederle, es que el registro no se puede acotar.
CODIGO_REGISTRO_ACOTADO = "registro_completo_con_alcance_acotado"


@router.get(
    "/audit-log",
    response_model=list[AuditLogRead],
    summary="Registro de actividades de la empresa, del mas reciente al mas antiguo",
    description=(
        "Todo lo que cambio por la ORM, con el antes y el despues. Exige "
        "`audit_log.read`.\n\n"
        "Responde **403** a quien este acotado a una planta: el registro no dice "
        "de que planta es cada cambio, asi que no se puede recortar, y mostrarlo "
        "entero le daria lo de las otras plantas. Esa persona lo consulta por "
        "registro, en su historial."
    ),
)
def list_audit_log(
    respuesta: Response,
    pagina: Pagina = Depends(paginacion),
    desde: date | None = Query(
        None, description="Primer dia, de calendario **de la empresa**, incluido."
    ),
    hasta: date | None = Query(
        None, description="Ultimo dia, de calendario de la empresa, **incluido entero**."
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    # **Acotado es acotado, tambien aca** (spec de RBAC, "el alcance de un rol
    # puede acotarse"). `audit_log` no tiene `facility_id`: decidir la planta de
    # cada fila obligaria a resolver la entidad de cada una. Hasta que haga
    # falta, se niega en vez de mostrar de mas.
    if instalaciones_permitidas(db) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "codigo": CODIGO_REGISTRO_ACOTADO,
                "mensaje": (
                    "Tu acceso esta acotado a una planta y el registro completo "
                    "abarca toda la empresa. Consulta el historial de cada registro."
                ),
            },
        )
    # **Del mas reciente al mas antiguo.** Sin orden, Postgres devuelve lo que le
    # quede comodo —en la practica, lo mas viejo primero—, y con el tope de la
    # pagina se verian siempre las mismas filas del principio.
    #
    # El nombre de quien actuo lo pone el servidor, con un LEFT JOIN bajo RLS:
    # resolverlo en el navegador obligaria a tener la lista de usuarios cargada.
    consulta = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.actor_user_id)
    # **Dias de calendario de la empresa, no instantes** ("eventos del 3 de
    # septiembre" es un dia en Chile). `hasta` incluye el dia entero.
    if desde is not None or hasta is not None:
        huso = ZoneInfo(huso_de(db, tenant_id))
        if desde is not None:
            consulta = consulta.where(AuditLog.occurred_at >= datetime.combine(desde, time.min, huso))
        if hasta is not None:
            consulta = consulta.where(
                AuditLog.occurred_at < datetime.combine(hasta + timedelta(days=1), time.min, huso)
            )
    filas = db.execute(
        consulta.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .offset(pagina.skip)
        .limit(pagina.pedir)
    ).all()
    leidas = [
        AuditLogRead.model_validate(entrada).model_copy(update={"actor_nombre": nombre})
        for entrada, nombre in filas
    ]
    return recortar(respuesta, leidas, pagina)
