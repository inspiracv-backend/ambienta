"""CRM simplificado: empresas, contactos, pipeline y actividades (epica #32)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ..crud.crm import (
    crud_crm_activity,
    crud_crm_company,
    crud_crm_contact,
    crud_crm_deal,
    crud_crm_stage,
)
from ..crud.organization import crud_contract
from ..deps import get_tenant_db, get_tenant_id
from ..models.crm import CrmStage
from ..models.organization import Contract
from ..schemas.crm import (
    ColumnaDelPipeline,
    CrmActivityCreate,
    CrmActivityRead,
    CrmActivityUpdate,
    CrmCompanyCreate,
    CrmCompanyRead,
    CrmCompanyUpdate,
    CrmContactCreate,
    CrmContactRead,
    CrmContactUpdate,
    CrmDealCreate,
    CrmDealRead,
    CrmDealUpdate,
    CrmStageCreate,
    CrmStageRead,
    CrmStageUpdate,
    MoverDeEtapa,
    PipelineRead,
    MontoPorMoneda,
    PromoverAContrato,
    ResultadoMover,
    ResultadoPromocion,
)
from ..services import crm as svc
from ._comun import borrar_o_404, obtener_o_404, validar_visible
from ._paginacion import POR_DEFECTO, TOPE_DE_PAGINA, Pagina, paginacion, recortar

router = APIRouter(prefix="/crm", tags=["crm"])


def _traducir(exc: svc.ErrorDeCrm) -> HTTPException:
    """Cada error del CRM a su codigo.

    `SinEtapas` es **409 y no 422**: el cuerpo esta bien y la peticion es
    legitima; lo que falta es configuracion de la empresa. Un 422 diria
    "corrige lo que mandaste", y no hay nada que corregir en el cuerpo.
    """
    if isinstance(
        exc,
        (
            svc.SinEtapas,
            svc.TratoNoGanado,
            svc.YaPromovido,
            # Las tres de configuracion del pipeline son del mismo tipo: el
            # cuerpo esta bien y lo que no corresponde es el estado en que
            # quedaria la empresa.
            svc.EtapaConTratos,
            svc.UltimaEtapaDeSuTipo,
            svc.EtapaNoDisponible,
        ),
    ):
        # 409 y no 422 por el mismo motivo que `SinEtapas`: el cuerpo esta
        # bien. Lo que no corresponde es el **estado** del trato, y eso no se
        # arregla corrigiendo lo que se mando.
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


# ── Etapas ────────────────────────────────────────────────────────────────


@router.get(
    "/stages",
    response_model=list[CrmStageRead],
    summary="Etapas del pipeline",
    description=(
        "En su orden, solo las activas. Son configurables por empresa (#78): "
        "una consultora ambiental y un gestor de residuos no venden igual."
    ),
)
def list_stages(db: Session = Depends(get_tenant_db), tenant_id: UUID = Depends(get_tenant_id)):
    """En su orden. Son configurables por empresa (#78)."""
    return svc.etapas_de(db, tenant_id)


@router.post(
    "/stages",
    response_model=CrmStageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una etapa",
    description=(
        "`kind` (`open` / `won` / `lost`) dice **que significa** la etapa para "
        "el sistema, independiente de como la llame la empresa. Sin el, medir "
        "la tasa de cierre obligaria a comparar nombres escritos a mano."
    ),
)
def create_stage(
    data: CrmStageCreate,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    fila = crud_crm_stage.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return fila


@router.get(
    "/stages/{stage_id}",
    response_model=CrmStageRead,
    summary="Ver una etapa",
    description="Una columna del kanban, con su orden y su `kind`.",
)
def get_stage(stage_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_crm_stage, db, stage_id, recurso="Etapa")


@router.patch(
    "/stages/{stage_id}",
    response_model=CrmStageRead,
    summary="Renombrar o reordenar una etapa",
    description=(
        "`position` es el orden en el kanban. Cambiar `kind` cambia que "
        "significa la etapa para el sistema, no solo su nombre: pasar una "
        "columna a `won` hace que los tratos que caigan ahi se cierren.\n\n"
        "**Responde 409** si el cambio dejaria el pipeline sin ninguna etapa "
        "activa de un tipo, o si desactiva una columna que todavia tiene "
        "tratos: los dejaria guardados y fuera del tablero. Renombrar y "
        "reordenar no tienen restriccion."
    ),
)
def update_stage(stage_id: UUID, data: CrmStageUpdate, db: Session = Depends(get_tenant_db)):
    fila = obtener_o_404(crud_crm_stage, db, stage_id, recurso="Etapa")
    # **Desactivar es retirar, y cambiar el `kind` puede dejar a la empresa sin
    # etapa de un tipo.** La misma comprobacion que el DELETE, o el DELETE
    # estaria protegido y este seria la puerta de al lado.
    try:
        svc.comprobar_cambio_de_etapa(db, fila, activa=data.active, kind=data.kind)
    except svc.ErrorDeCrm as exc:
        raise _traducir(exc) from None
    actualizada = crud_crm_stage.update(db, db_obj=fila, obj_in=data)
    db.commit()
    return actualizada


@router.delete(
    "/stages/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirar una etapa",
    description=(
        "Borrado logico: los tratos que pasaron por ella conservan su "
        "historia.\n\n"
        "**Responde 409 en dos casos.** Si la columna todavia tiene tratos, "
        "porque `pipeline` recorre solo las activas y quedarian invisibles — en "
        "la base y fuera del tablero, que es peor que borrados. Y si es la "
        "ultima activa de su tipo, porque sin una `open` los tratos nuevos "
        "nacen en una columna de cierre, sin una `won` no se puede promover a "
        "contrato, y sin una `lost` no hay donde registrar una venta perdida "
        "con su motivo.\n\n"
        "`active = false` **no es la via corta**: hace lo mismo y pasa por las "
        "mismas comprobaciones."
    ),
)
def delete_stage(stage_id: UUID, db: Session = Depends(get_tenant_db)):
    fila = obtener_o_404(crud_crm_stage, db, stage_id, recurso="Etapa")
    try:
        svc.retirar_etapa(db, fila)
    except svc.ErrorDeCrm as exc:
        raise _traducir(exc) from None
    db.commit()


# ── Empresas ──────────────────────────────────────────────────────────────


@router.get(
    "/companies",
    response_model=list[CrmCompanyRead],
    summary="Empresas del CRM",
    description=(
        "Prospectos y clientes. **No son `tenants`**: `tenants` son las "
        "empresas que usan la plataforma, y estas son con las que la empresa "
        "hace negocio — la mayoria sin cuenta."
    ),
)
def list_companies(
    respuesta: Response,
    pagina: Pagina = Depends(paginacion),
    db: Session = Depends(get_tenant_db),
):
    """Prospectos y clientes.

    **No son `tenants`.** `tenants` son las empresas que usan la plataforma;
    estas son con las que la empresa hace negocio, y la mayoria no tiene cuenta.
    """
    return recortar(
        respuesta,
        crud_crm_company.get_multi(db, skip=pagina.skip, limit=pagina.pedir),
        pagina,
    )


@router.post(
    "/companies",
    response_model=CrmCompanyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una empresa",
    description=(
        "Un prospecto o un cliente. **El RUT no es obligatorio**: a un "
        "prospecto se le sigue la pista antes de tenerlo, y exigirlo "
        "obligaria a inventarlo para poder anotarlo.\n\n"
        "`client_tenant_id` **no se acepta del cuerpo**: es una clave "
        "foranea a `tenants`, y las claves foraneas no pasan por RLS. Se "
        "fija al promover el trato ganado a contrato."
    ),
)
def create_company(
    data: CrmCompanyCreate,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    fila = crud_crm_company.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return fila


@router.get(
    "/companies/{company_id}",
    response_model=CrmCompanyRead,
    summary="Ver una empresa",
    description="La ficha del prospecto o cliente.",
)
def get_company(company_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_crm_company, db, company_id, recurso="Empresa")


@router.patch(
    "/companies/{company_id}",
    response_model=CrmCompanyRead,
    summary="Editar una empresa",
    description=(
        "`status` distingue prospecto de cliente. Pasa a `client` solo al "
        "promover un trato ganado, no a mano: asi la lista de clientes "
        "coincide con la de contratos."
    ),
)
def update_company(
    company_id: UUID, data: CrmCompanyUpdate, db: Session = Depends(get_tenant_db)
):
    fila = obtener_o_404(crud_crm_company, db, company_id, recurso="Empresa")
    actualizada = crud_crm_company.update(db, db_obj=fila, obj_in=data)
    db.commit()
    return actualizada


@router.delete(
    "/companies/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirar una empresa",
    description=(
        "Borrado logico: sus tratos y actividades se conservan, porque son "
        "el historial de por que se dejo de trabajar con ella."
    ),
)
def delete_company(company_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_crm_company, db, company_id, recurso="Empresa")
    db.commit()


# ── Contactos ─────────────────────────────────────────────────────────────


@router.get(
    "/contacts",
    response_model=list[CrmContactRead],
    summary="Contactos del CRM",
    description="Las personas de las empresas con las que se hace negocio.",
)
def list_contacts(
    respuesta: Response,
    pagina: Pagina = Depends(paginacion),
    db: Session = Depends(get_tenant_db),
):
    return recortar(
        respuesta,
        crud_crm_contact.get_multi(db, skip=pagina.skip, limit=pagina.pedir),
        pagina,
    )


@router.post(
    "/contacts",
    response_model=CrmContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un contacto",
    description=(
        "**Un solo contacto principal por empresa**, y lo impide un indice "
        "unico: dos principales no es un dato, es la ausencia de una "
        "decision, y la pantalla tendria que elegir uno igual al mandar un "
        "correo."
    ),
)
def create_contact(
    data: CrmContactCreate,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    # La empresa viene en el cuerpo y **las claves foraneas no pasan por RLS**:
    # sin esto, la empresa B podria colgar un contacto de la ficha de la A.
    validar_visible(crud_crm_company, db, data.crm_company_id, campo="crm_company_id")
    fila = crud_crm_contact.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return fila


@router.get(
    "/contacts/{contact_id}",
    response_model=CrmContactRead,
    summary="Ver un contacto",
    description="La ficha de la persona, con su empresa.",
)
def get_contact(contact_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_crm_contact, db, contact_id, recurso="Contacto")


@router.patch(
    "/contacts/{contact_id}",
    response_model=CrmContactRead,
    summary="Editar un contacto",
    description=(
        "Marcarlo principal exige que ningun otro de la misma empresa lo "
        "sea; la base responde 409 si ya hay uno."
    ),
)
def update_contact(
    contact_id: UUID, data: CrmContactUpdate, db: Session = Depends(get_tenant_db)
):
    fila = obtener_o_404(crud_crm_contact, db, contact_id, recurso="Contacto")
    actualizada = crud_crm_contact.update(db, db_obj=fila, obj_in=data)
    db.commit()
    return actualizada


@router.delete(
    "/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirar un contacto",
    description=(
        "Borrado logico. Los tratos que lo tenian asignado quedan sin "
        "contacto, no se borran: el trato sigue vivo aunque la persona se "
        "haya ido de la empresa."
    ),
)
def delete_contact(contact_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_crm_contact, db, contact_id, recurso="Contacto")
    db.commit()


# ── Oportunidades ─────────────────────────────────────────────────────────


@router.get(
    "/deals",
    response_model=list[CrmDealRead],
    summary="Oportunidades",
    description=(
        "La lista plana. Para dibujar el kanban esta `/crm/pipeline`, que "
        "las trae ya agrupadas por columna y con los totales."
    ),
)
def list_deals(
    respuesta: Response,
    pagina: Pagina = Depends(paginacion),
    db: Session = Depends(get_tenant_db),
):
    return recortar(
        respuesta,
        crud_crm_deal.get_multi(db, skip=pagina.skip, limit=pagina.pedir),
        pagina,
    )


@router.post(
    "/deals",
    response_model=CrmDealRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una oportunidad",
    description=(
        "Sin `stage_id`, entra en la **primera etapa abierta** del pipeline. Se "
        "prefiere la primera abierta y no la primera a secas: si alguien "
        "reordena y deja 'Perdido' arriba, un trato nuevo naceria perdido."
    ),
)
def create_deal(
    data: CrmDealCreate,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    validar_visible(crud_crm_company, db, data.crm_company_id, campo="crm_company_id")
    validar_visible(crud_crm_contact, db, data.crm_contact_id, campo="crm_contact_id")
    validar_visible(crud_crm_stage, db, data.stage_id, campo="stage_id")

    cuerpo = data.model_dump(exclude={"stage_id"})
    try:
        deal = svc.crear_deal(db, tenant_id, cuerpo, data.stage_id)
    except svc.ErrorDeCrm as exc:
        raise _traducir(exc) from None
    db.commit()
    return deal


@router.get(
    "/deals/{deal_id}",
    response_model=CrmDealRead,
    summary="Ver una oportunidad",
    description=(
        "`closed_at` con valor significa que el trato esta cerrado, ganado "
        "o perdido; `lost_reason` dice por que si se perdio."
    ),
)
def get_deal(deal_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_crm_deal, db, deal_id, recurso="Oportunidad")


@router.patch(
    "/deals/{deal_id}",
    response_model=CrmDealRead,
    summary="Editar una oportunidad",
    description=(
        "Los datos del trato. **La etapa no se cambia aca**: para eso esta "
        "`/deals/{deal_id}/stage`, porque mover de columna cierra el trato, "
        "exige motivo al perder o lo reabre — y todo eso se perderia en un "
        "PATCH generico de `stage_id`."
    ),
)
def update_deal(deal_id: UUID, data: CrmDealUpdate, db: Session = Depends(get_tenant_db)):
    """Edita los datos del trato. **La etapa no**: para eso esta `/stage`."""
    fila = obtener_o_404(crud_crm_deal, db, deal_id, recurso="Oportunidad")
    validar_visible(crud_crm_contact, db, data.crm_contact_id, campo="crm_contact_id")
    actualizada = crud_crm_deal.update(db, db_obj=fila, obj_in=data)
    db.commit()
    return actualizada


@router.delete(
    "/deals/{deal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirar una oportunidad",
    description=(
        "Borrado logico. Un trato perdido **no se borra**: se mueve a la "
        "etapa `lost` con su motivo, que es lo que deja aprender por que "
        "se pierde. Esto es para lo que se creo por error."
    ),
)
def delete_deal(deal_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_crm_deal, db, deal_id, recurso="Oportunidad")
    db.commit()


@router.post(
    "/deals/{deal_id}/stage",
    response_model=ResultadoMover,
    summary="Mover el trato a otra etapa",
    description=(
        "Arrastrar una tarjeta en el kanban. **No es editar un campo**: segun a "
        "donde vaya, el trato se cierra, exige motivo o se reabre.\n\n"
        "- A una etapa `won` o `lost` **se cierra**, y `closed_at` deja escrito "
        "cuando — que es lo que permite medir cuanto dura un ciclo de venta.\n"
        "- A `lost` **exige motivo**: aprender por que se pierde es la razon de "
        "tener un pipeline.\n"
        "- De vuelta a `open` **se reabre** y se limpia el cierre; si no, "
        "quedaria un trato activo con fecha de cierre y las metricas lo "
        "contarian de los dos lados.\n\n"
        "La respuesta trae `efectos` para que la pantalla pueda decir que paso, "
        "en vez de que la persona lo descubra cuando el trato desaparece de sus "
        "pendientes."
    ),
)
def mover_de_etapa(
    deal_id: UUID,
    datos: MoverDeEtapa,
    db: Session = Depends(get_tenant_db),
):
    deal = obtener_o_404(crud_crm_deal, db, deal_id, recurso="Oportunidad")
    validar_visible(crud_crm_stage, db, datos.stage_id, campo="stage_id")
    etapa = db.get(CrmStage, datos.stage_id)
    if etapa is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La etapa no corresponde a esta empresa.",
        )

    try:
        efectos = svc.mover_de_etapa(db, deal, etapa, datos.motivo)
    except svc.ErrorDeCrm as exc:
        raise _traducir(exc) from None
    db.commit()
    return ResultadoMover(deal=CrmDealRead.model_validate(deal), efectos=efectos)


@router.post(
    "/deals/{deal_id}/promover",
    response_model=ResultadoPromocion,
    summary="Promover el trato ganado a contrato",
    description=(
        "Cierra el circulo entre vender y prestar el servicio (RF-66): el trato "
        "ganado queda enlazado al contrato que lo materializo, y la ficha "
        "comercial deja de ser un prospecto.\n\n"
        "**No crea el contrato.** Crearlo exige que el cliente ya sea un tenant "
        "de la plataforma, que es un alta con su propio flujo; hacerlo aca de "
        "paso produciria empresas a medias creadas por arrastrar una tarjeta.\n\n"
        "Se niega en tres casos, todos con **409**: si el trato no esta en una "
        "etapa de ganado, si ya apunta a otro contrato, y si el contrato "
        "corresponde a un cliente distinto del que nombra la ficha."
    ),
)
def promover_a_contrato(
    deal_id: UUID,
    datos: PromoverAContrato,
    db: Session = Depends(get_tenant_db),
):
    deal = obtener_o_404(crud_crm_deal, db, deal_id, recurso="Oportunidad")
    # `contract_id` viene del cuerpo, asi que pasa por la misma comprobacion
    # que cualquier otra clave foranea: las FK **no pasan por RLS**, y sin esto
    # una empresa podria enlazar su trato con el contrato de otra.
    validar_visible(crud_contract, db, datos.contract_id, campo="contract_id")
    contrato = db.get(Contract, datos.contract_id)
    if contrato is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="contract_id no corresponde a un registro de esta empresa.",
        )

    etapa = db.get(CrmStage, deal.stage_id)
    try:
        efectos = svc.promover_a_contrato(db, deal, contrato, etapa)
    except svc.ErrorDeCrm as exc:
        raise _traducir(exc) from None
    db.commit()
    db.refresh(deal)
    return ResultadoPromocion(
        deal=CrmDealRead.model_validate(deal), efectos=efectos
    )


# ── Actividades ───────────────────────────────────────────────────────────


@router.get(
    "/activities",
    response_model=list[CrmActivityRead],
    summary="Linea de tiempo",
    description=(
        "De lo mas nuevo a lo mas viejo.\n\n"
        "Con `company_id` incluye **lo de sus tratos y sus contactos**, no "
        "solo lo colgado de la empresa: quien abre la ficha de un cliente "
        "quiere ver todo lo que paso con el, no la parte que alguien recordo "
        "anotar en el sitio exacto."
    ),
)
def list_activities(
    deal_id: UUID | None = None,
    company_id: UUID | None = None,
    # Acotado, pero **sin `skip`**: `linea_de_tiempo` no tiene desplazamiento,
    # asi que aceptar uno seria un parametro que se ignora en silencio. Lo que
    # esto impide es lo unico que estaba abierto — pedir la tabla entera.
    limit: int = Query(
        default=POR_DEFECTO,
        ge=1,
        le=TOPE_DE_PAGINA,
        description=f'Cuantas actividades devolver, hasta {TOPE_DE_PAGINA}.',
    ),
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """La linea de tiempo, de lo mas nuevo a lo mas viejo.

    Con `company_id` incluye **lo de sus tratos y sus contactos**, no solo lo
    colgado de la empresa: quien abre la ficha de un cliente quiere ver todo lo
    que paso con el, no la parte que alguien recordo anotar en el sitio exacto.
    """
    return svc.linea_de_tiempo(
        db, tenant_id, deal_id=deal_id, company_id=company_id, limite=limit
    )


@router.post(
    "/activities",
    response_model=CrmActivityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Anotar una llamada, correo, reunion o nota",
    description=(
        "Cuelga de **exactamente uno**: empresa, contacto u oportunidad. "
        "Ninguno seria una actividad huerfana que no aparece en ninguna ficha; "
        "dos, la misma llamada contada dos veces en la linea de tiempo."
    ),
)
def create_activity(
    data: CrmActivityCreate,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    cuerpo = data.model_dump(exclude_none=False)
    try:
        svc.validar_padre_de_actividad(cuerpo)
    except svc.ErrorDeCrm as exc:
        raise _traducir(exc) from None

    validar_visible(crud_crm_company, db, data.crm_company_id, campo="crm_company_id")
    validar_visible(crud_crm_contact, db, data.crm_contact_id, campo="crm_contact_id")
    validar_visible(crud_crm_deal, db, data.crm_deal_id, campo="crm_deal_id")

    fila = crud_crm_activity.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return fila


@router.get(
    "/activities/{activity_id}",
    response_model=CrmActivityRead,
    summary="Ver una actividad",
    description="Una llamada, un correo, una reunion o una nota.",
)
def get_activity(activity_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_crm_activity, db, activity_id, recurso="Actividad")


@router.patch(
    "/activities/{activity_id}",
    response_model=CrmActivityRead,
    summary="Editar una actividad",
    description=(
        "El padre **no se cambia**: mover una llamada de un trato a otro "
        "reescribiria dos lineas de tiempo a la vez. Se anota de nuevo en "
        "el sitio correcto y se retira la equivocada."
    ),
)
def update_activity(
    activity_id: UUID, data: CrmActivityUpdate, db: Session = Depends(get_tenant_db)
):
    fila = obtener_o_404(crud_crm_activity, db, activity_id, recurso="Actividad")
    actualizada = crud_crm_activity.update(db, db_obj=fila, obj_in=data)
    db.commit()
    return actualizada


@router.delete(
    "/activities/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirar una actividad",
    description="Borrado logico: desaparece de la linea de tiempo y queda el rastro.",
)
def delete_activity(activity_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_crm_activity, db, activity_id, recurso="Actividad")
    db.commit()


# ── El kanban ─────────────────────────────────────────────────────────────


@router.get(
    "/pipeline",
    response_model=PipelineRead,
    tags=["business-logic"],
    summary="El pipeline entero, listo para dibujar",
    description=(
        "Columnas, tarjetas y totales en una sola peticion, en vez de una por "
        "etapa.\n\n"
        "**Los totales se calculan sobre todo lo que hay, no sobre lo que se "
        "devuelve.** Cada columna trae hasta 50 tarjetas; sumar solo las "
        "visibles daria un monto menor que el real en cuanto una columna pase "
        "del tope, y ese numero se cita despues en una reunion como si fuera el "
        "pipeline completo. `truncado` dice si algo se corto.\n\n"
        "**Y se suma por moneda, no todo junto:** `montos` trae una entrada por "
        "moneda. Un trato de 1.000 CLP y otro de 1.000 USD sumados a secas dan "
        "`2000`, que no es plata de ninguna clase."
    ),
)
def ver_pipeline(
    db: Session = Depends(get_tenant_db), tenant_id: UUID = Depends(get_tenant_id)
):
    datos = svc.pipeline(db, tenant_id)
    return PipelineRead(
        columnas=[
            ColumnaDelPipeline(
                stage=CrmStageRead.model_validate(c["stage"]),
                deals=[CrmDealRead.model_validate(d) for d in c["deals"]],
                total_deals=c["total_deals"],
                montos=[
                    MontoPorMoneda(moneda=m, total=t) for m, t in c["montos"]
                ],
            )
            for c in datos["columnas"]
        ],
        truncado=datos["truncado"],
    )
