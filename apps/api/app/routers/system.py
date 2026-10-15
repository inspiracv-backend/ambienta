from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alcance import instalaciones_permitidas
from ..auth import CurrentUser
from ..deps import (
    exigir_admin_global,
    get_tenant_db,
    get_tenant_id,
    token_crudo,
)
from ..services import ai_service as svc_ai
from ..models.organization import User
from ..services.husos import huso_de
from ..models.system import AuditLog
from ._paginacion import Pagina, paginacion, recortar
from ..schemas.system import AuditLogRead, EstadoDeLosAgentesIA

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


#: La descripcion de Swagger, por parrafos. Se une con saltos de linea en vez de
#: escribirlos a mano: una cadena con `\n` escapado dentro de un script
#: generador es como se rompio este archivo la primera vez.
_PARRAFOS_AGENTES = [
    "**Solo plataforma.** Devuelve la ultima corrida de cada trabajo de fondo "
    "del servicio de IA: cuando empezo, cuando termino, cuantos elementos "
    "proceso y si fallo.",
    "Existe porque **un trabajo que falla en silencio es el peor estado "
    "posible** en este producto: la ingesta deja de indexar, el chatbot empieza "
    "a responder «no tengo informacion suficiente» y nada dice que la causa es "
    "un cron caido hace dos semanas. El sintoma se lee como que el asistente es "
    "malo.",
    "La API es la fachada: el AI Service no se publica a internet. Sin "
    "`AI_SERVICE_URL` responde **503** diciendo que falta.",
]


@router.get(
    "/agentes-ia",
    response_model=EstadoDeLosAgentesIA,
    summary="Estado de los trabajos de ingesta y monitoreo del AI Service",
    description="\n\n".join(_PARRAFOS_AGENTES),
    tags=["business-logic"],
)
def estado_de_los_agentes_ia(
    peticion: Request,
    # **La raiz `system` esta exenta del permiso derivado de la ruta**, asi que
    # sin esta guarda explicita el endpoint no pediria nada. Es exactamente como
    # `/system/audit-log` quedo sin pedir permiso: el guardia general salia
    # antes de mirar.
    #
    # Y es `exigir_admin_global` y no un permiso de empresa porque el estado de
    # los trabajos no pertenece a ninguna empresa. Su mensaje de rechazo habla
    # de "administrar empresas" —es generico— pero la regla es una sola, y
    # duplicarla es como aparecen dos reglas que divergen.
    usuario: CurrentUser = Depends(exigir_admin_global),
    tenant_id: UUID = Depends(get_tenant_id),
    token: str | None = Depends(token_crudo),
):
    """Reenvia la consulta de estado con la identidad de quien pregunta.

    ## Sobre la identidad de plataforma

    El contrato del AI Service exige el claim `tenant_id` incluso aca, y el
    informe de integracion lo marca como algo a resolver: *"una cuenta global
    puede no tener empresa"*. **En este esquema no lo es.** `users.tenant_id` es
    `NOT NULL` y `crear-admin-global` crea la empresa `platform`, asi que un
    `platform_admin` siempre tiene empresa. No hace falta cambiar el contrato ni
    asignarle una empresa real a la cuenta global.
    """
    encabezados = svc_ai.cabeceras(
        token=token,
        tenant_id=tenant_id,
        acepta="application/json",
        request_id=peticion.headers.get("x-request-id"),
    )
    return svc_ai.estado_de_los_agentes(encabezados=encabezados)
