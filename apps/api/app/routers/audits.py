from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud.audit import (
    crud_action_plan,
    crud_audit,
    crud_audit_item,
    crud_metodologia,
    crud_nonconformity,
    crud_severidad,
    crud_veredicto_de_proceso,
)
from ..auth import CurrentUser
from ..deps import get_current_user, get_tenant_db, get_tenant_id
from ..services import audits as svc_audits
from ..services import catalogos_de_mejora as svc_catalogos
from ..services import informe_de_auditoria as svc_informe
from ..crud.compliance import crud_article_compliance
from ..crud.organization import crud_process, crud_user
from ..models.audit import AuditItem, AuditParticipant, AuditProcessResult
from ..models.organization import User
from ._paginacion import Pagina, paginacion, recortar
from ._comun import (
    CRUDAsociacion,
    borrar_o_404,
    listar_por_padre,
    obtener_o_404,
    validar_visible,
    verificar_padre,
)
from ..schemas.audit import (
    AuditItemUpdate,
    InformeDeAuditoria,
    VeredictoDeProcesoCreate,
    VeredictoDeProcesoCreateAnidado,
    VeredictoDeProcesoRead,
    VeredictoDeProcesoUpdate,
    MetodologiaCreate,
    MetodologiaRead,
    MetodologiaUpdate,
    SeveridadCreate,
    SeveridadRead,
    SeveridadUpdate,
    CoberturaDeAuditoria,
    AuditItemRead,
    AuditItemCreate,
    AuditItemCreateAnidado,
    ActionPlanCreate,
    AuditParticipantCreateAnidado,
    AuditParticipantRead,
    AuditParticipantUpdate,
    ActionPlanRead,
    ActionPlanUpdate,
    AuditCreate,
    AuditRead,
    AuditUpdate,
    NonconformityCreate,
    NonconformityRead,
    NonconformityUpdate,
)

router = APIRouter(prefix="/audits", tags=["audits"])


@router.get("/", response_model=list[AuditRead])
def list_audits(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_audit.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.get("/{audit_id}", response_model=AuditRead)
def get_audit(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_audit.get(db, audit_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    return obj


@router.post("/", response_model=AuditRead, status_code=status.HTTP_201_CREATED)
def create_audit(
    data: AuditCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_audit.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{audit_id}", response_model=AuditRead)
def update_audit(audit_id: UUID, data: AuditUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_audit.get(db, audit_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    obj = crud_audit.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Nonconformities ──────────────────────────────────────────────────────

@router.get("/nonconformities/", response_model=list[NonconformityRead], tags=["nonconformities"])
def list_nonconformities(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_nonconformity.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.post("/nonconformities/", response_model=NonconformityRead, status_code=status.HTTP_201_CREATED, tags=["nonconformities"])
def create_nonconformity(
    data: NonconformityCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Registra un hallazgo, con la severidad y el plazo de **esta** empresa.

    Dos cosas que no hacia antes:

    - La severidad se comprueba contra el catalogo de la empresa (RF-100). El
      CHECK de la columna sigue siendo la barrera de la base; esta es mas
      estrecha, y es la que hace que configurar el catalogo signifique algo.
    - `due_date` **se calcula** desde el plazo del nivel, si la empresa lo
      declaro. Esa columna existia y nadie la llenaba: el compromiso de cierre
      vivia en la cabeza de alguien. Lo que venga en el cuerpo manda —una
      autoridad puede fijar otra fecha— y el calculo solo cubre el vacio.
    """
    try:
        nivel = svc_catalogos.comprobar_severidad(db, tenant_id, data.severity)
    except svc_catalogos.SinNivelesDeSeveridad as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None
    except svc_catalogos.SeveridadNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None

    validar_visible(
        crud_metodologia,
        db,
        data.root_cause_methodology_id,
        campo="root_cause_methodology_id",
    )

    obj = crud_nonconformity.create(db, obj_in=data, tenant_id=tenant_id)
    if obj.due_date is None:
        obj.due_date = svc_catalogos.fecha_limite(nivel, date.today())
    db.commit()
    return obj


@router.patch("/nonconformities/{nc_id}", response_model=NonconformityRead, tags=["nonconformities"])
def update_nonconformity(nc_id: UUID, data: NonconformityUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_nonconformity.get(db, nc_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nonconformity not found")
    obj = crud_nonconformity.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Action Plans ─────────────────────────────────────────────────────────

@router.get("/action-plans/", response_model=list[ActionPlanRead], tags=["action-plans"])
def list_action_plans(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_action_plan.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.post("/action-plans/", response_model=ActionPlanRead, status_code=status.HTTP_201_CREATED, tags=["action-plans"])
def create_action_plan(
    data: ActionPlanCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_action_plan.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/action-plans/{plan_id}", response_model=ActionPlanRead, tags=["action-plans"])
def update_action_plan(plan_id: UUID, data: ActionPlanUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_action_plan.get(db, plan_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
    obj = crud_action_plan.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Business Logic ──────────────────────────────────────────────────────

@router.post("/{audit_id}/advance", response_model=AuditRead, tags=["business-logic"])
def advance_status(audit_id: UUID, new_status: str, db: Session = Depends(get_tenant_db)):
    from ..services.audits import advance_audit_status
    try:
        obj = advance_audit_status(db, audit_id, new_status)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{audit_id}/summary", tags=["business-logic"])
def audit_summary(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    from ..services.audits import get_audit_summary
    try:
        return get_audit_summary(db, audit_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/nonconformities/{nc_id}/close",
    response_model=NonconformityRead,
    tags=["business-logic"],
    summary="Cerrar un registro de mejora",
    description=(
        "**Exige una verificacion de eficacia afirmativa** (ISO 14001 10.2.1 d): "
        "al menos un plan de accion `verified`, y ninguno pendiente.\n\n"
        "Responde **409** cuando falta, y no 422: el cuerpo esta bien y la "
        "peticion es legitima; lo que no corresponde es el **estado** del "
        "registro, y eso no se arregla corrigiendo lo que se mando.\n\n"
        "Un plan `cancelled` no bloquea —cancelar es decidir que ese trabajo no "
        "se hace— pero tampoco alcanza para cerrar: cancelar todo no es haber "
        "verificado nada."
    ),
)
def close_nc(nc_id: UUID, closure_notes: str = "", db: Session = Depends(get_tenant_db)):
    from ..services.audits import SinVerificarLaEficacia, close_nonconformity

    try:
        obj = close_nonconformity(db, nc_id, closure_notes)
        db.commit()
        return obj
    except SinVerificarLaEficacia as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/action-plans/{plan_id}/verify",
    response_model=ActionPlanRead,
    tags=["business-logic"],
    summary="Verificar la eficacia de un plan de accion",
    description=(
        "Deja escrito **quien** verifico que la accion funciono y cuando. Es lo "
        "que habilita cerrar el registro.\n\n"
        "Con `success=false` el plan vuelve a `in_progress`: la verificacion "
        "concluyo que no funciono, y el trabajo sigue.\n\n"
        "Responde **409** si la sesion no esta asociada a un usuario de la "
        "empresa. No se toma a otra persona en su lugar: ante una auditoria la "
        "pregunta no es si se verifico, es quien."
    ),
)
def verify_plan(
    plan_id: UUID,
    success: bool = True,
    db: Session = Depends(get_tenant_db),
    usuario: CurrentUser = Depends(get_current_user),
):
    """Verifica la eficacia de un plan de accion.

    **Este endpoint respondia 500 en el 100 % de los casos.** Le pasaba el
    `tenant_id` al servicio donde este espera el id de quien verifica, y
    `action_plans.verified_by` tiene clave foranea contra `users`: el `UPDATE`
    violaba la restriccion. Medido el 4-sep contra la base real.

    Nadie se entero porque `audits.py` no tenia una sola prueba que llamara a
    sus endpoints —30 operaciones—, y porque verificar la eficacia es el paso
    que solo se ejecuta al final de un ciclo largo.
    """
    from ..services.audits import verify_action_plan

    verificador = (
        db.scalar(select(User).where(User.clerk_id == usuario.user_id))
        if usuario.user_id
        else None
    )
    if verificador is None:
        # Mismo criterio que aprobar un documento: no se inventa quien firma.
        # Tomar al primer administrador dejaria escrito que esa persona
        # verifico algo que no verifico, y es lo que un auditor lee.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se puede registrar quien verifica: la sesion no esta "
                "asociada a un usuario de esta empresa. Verificar la eficacia "
                "exige una sesion identificada."
            ),
        )

    try:
        obj = verify_action_plan(db, plan_id, verificador.id, success)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{audit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_audit(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una auditoria. Sus hallazgos y no conformidades no se tocan:
    una no conformidad sobrevive a la auditoria que la origino."""
    borrar_o_404(crud_audit, db, audit_id, recurso="Audit")


@router.delete("/nonconformities/{nc_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["nonconformities"])
def delete_nonconformity(nc_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una no conformidad registrada por error.

    Cerrarla es otra cosa y va por `/nonconformities/{id}/close`: cerrar
    significa que se resolvio, esto que no debio existir.
    """
    borrar_o_404(crud_nonconformity, db, nc_id, recurso="Nonconformity")


@router.delete("/action-plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["action-plans"])
def delete_action_plan(plan_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_action_plan, db, plan_id, recurso="ActionPlan")


@router.get("/nonconformities/{nc_id}", response_model=NonconformityRead, tags=["nonconformities"])
def get_nonconformity(nc_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_nonconformity, db, nc_id, recurso="Nonconformity")


@router.get("/action-plans/{plan_id}", response_model=ActionPlanRead, tags=["action-plans"])
def get_action_plan(plan_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_action_plan, db, plan_id, recurso="ActionPlan")


# ── Participantes de una auditoria (clave compuesta, anidada) ──────────────

crud_participante = CRUDAsociacion(AuditParticipant, "audit_id", "user_id")


@router.get("/{audit_id}/participants", response_model=list[AuditParticipantRead], tags=["audits"])
def list_participants(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    return crud_participante.listar(db, audit_id)


@router.post("/{audit_id}/participants/{user_id}", response_model=AuditParticipantRead, status_code=status.HTTP_201_CREATED, tags=["audits"])
def add_participant(
    audit_id: UUID,
    user_id: UUID,
    data: AuditParticipantCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Suma a alguien a la auditoria.

    El usuario va en el path y no en el cuerpo para que la URL identifique por
    completo la fila: la clave es (audit_id, user_id).
    """
    obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    validar_visible(crud_user, db, user_id, campo="user_id")
    if crud_participante.obtener(db, audit_id, user_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esa persona ya participa en la auditoria.",
        )
    obj = crud_participante.crear(db, padre_id=audit_id, hijo_id=user_id, datos=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{audit_id}/participants/{user_id}", response_model=AuditParticipantRead, tags=["audits"])
def update_participant(
    audit_id: UUID, user_id: UUID, data: AuditParticipantUpdate, db: Session = Depends(get_tenant_db)
):
    obj = crud_participante.obtener(db, audit_id, user_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    obj = crud_participante.actualizar(db, db_obj=obj, datos=data)
    db.commit()
    return obj


@router.delete("/{audit_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["audits"])
def remove_participant(audit_id: UUID, user_id: UUID, db: Session = Depends(get_tenant_db)):
    """Saca a alguien de la auditoria. Borrado logico: quien participo es
    parte del registro de esa auditoria, aunque despues se le retire."""
    if crud_participante.borrar(db, padre_id=audit_id, hijo_id=user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    db.commit()


@router.get("/{audit_id}/participants/{user_id}", response_model=AuditParticipantRead, tags=["audits"])
def get_participant(audit_id: UUID, user_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_participante.obtener(db, audit_id, user_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return obj


@router.get(
    "/{audit_id}/coverage",
    response_model=CoberturaDeAuditoria,
    tags=["business-logic"],
    summary="Cuanto de lo aplicable miro esta auditoria",
    description=(
        "**El numero que falta para leer un resumen sin equivocarse.** Sin "
        "cobertura, una auditoria que reviso 3 de 50 requisitos y no encontro "
        "nada se lee identica a una que los reviso los 50: las dos dicen "
        "«0 no conformes».\n\n"
        "El denominador son los articulos evaluados de la planta auditada, o "
        "los de toda la empresa si la auditoria no declara planta. El numerador "
        "son los **distintos** articulos que el checklist referencia: dos "
        "preguntas sobre el mismo articulo no lo cubren dos veces.\n\n"
        "`porcentaje` es `null` —no cero— cuando no hay nada aplicable."
    ),
)
def cobertura_de_auditoria(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    auditoria = obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    return CoberturaDeAuditoria(**svc_audits.cobertura(db, auditoria))


# ── Hallazgos de una auditoria ─────────────────────────────────────────────

@router.get("/{audit_id}/items", response_model=list[AuditItemRead], tags=["audits"])
def list_audit_items(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    return listar_por_padre(AuditItem, db, audit_id, campo="audit_id")


@router.post("/{audit_id}/items", response_model=AuditItemRead, status_code=status.HTTP_201_CREATED, tags=["audits"])
def create_audit_item(
    audit_id: UUID,
    data: AuditItemCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obtener_o_404(crud_audit, db, audit_id, recurso="Audit")
    # Claves foraneas del cuerpo: **no pasan por RLS**. Sin esto, una empresa
    # podria colgar su pregunta de la evaluacion de otra — la misma fuga que ya
    # se midio en `POST /obligations/`.
    validar_visible(
        crud_article_compliance,
        db,
        data.article_compliance_id,
        campo="article_compliance_id",
    )
    validar_visible(crud_user, db, data.auditor_user_id, campo="auditor_user_id")
    validar_visible(crud_process, db, data.process_id, campo="process_id")

    datos = data.model_dump()
    datos["audit_id"] = audit_id
    if datos.get("sequence") is None:
        datos["sequence"] = svc_audits.siguiente_secuencia(db, audit_id)

    # Una `sequence` repetida la rechaza `uq_audit_items_seq`, y el manejador
    # global de `IntegrityError` ya la traduce a **409 nombrando la
    # restriccion**. No se envuelve aca: `CRUDBase.create` hace `flush` por
    # dentro, asi que el error salta antes de este punto y un `try` alrededor
    # del `commit` seria una guarda que nunca se cumple — proteccion aparente.
    obj = crud_audit_item.create(db, obj_in=AuditItemCreate(**datos), tenant_id=tenant_id)
    db.commit()
    return obj


@router.get("/{audit_id}/items/{item_id}", response_model=AuditItemRead, tags=["audits"])
def get_audit_item(audit_id: UUID, item_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_audit_item, db, item_id, recurso="AuditItem")
    return verificar_padre(obj, audit_id, campo="audit_id")


@router.patch("/{audit_id}/items/{item_id}", response_model=AuditItemRead, tags=["audits"])
def update_audit_item(audit_id: UUID, item_id: UUID, data: AuditItemUpdate, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_audit_item, db, item_id, recurso="AuditItem")
    verificar_padre(obj, audit_id, campo="audit_id")
    validar_visible(
        crud_article_compliance,
        db,
        data.article_compliance_id,
        campo="article_compliance_id",
    )
    validar_visible(crud_user, db, data.auditor_user_id, campo="auditor_user_id")

    obj = crud_audit_item.update(db, db_obj=obj, obj_in=data)
    # **Al responder se anota cuando.** Sin esa marca no se puede decir si la
    # auditoria se contesto durante su ejecucion o despues de cerrarla, que es
    # justo lo que revisa un certificador. La pone el servidor: por eso
    # `assessed_at` no esta en el cuerpo.
    if data.result is not None and data.result != "pending":
        obj.assessed_at = datetime.now(timezone.utc)

    # **Sin `db.refresh()` despues del commit.** El commit cierra la
    # transaccion y con ella se va el tenant declarado, asi que la recarga ve
    # cero filas y revienta con `Could not refresh instance`. El objeto ya
    # tiene los valores que se le pusieron; no hay nada que volver a leer.
    db.commit()
    return obj


@router.delete("/{audit_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["audits"])
def delete_audit_item(audit_id: UUID, item_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira un hallazgo registrado por error. Las no conformidades que haya
    originado no se tocan: viven mas alla del hallazgo."""
    obj = obtener_o_404(crud_audit_item, db, item_id, recurso="AuditItem")
    verificar_padre(obj, audit_id, campo="audit_id")
    borrar_o_404(crud_audit_item, db, item_id, recurso="AuditItem")


# -- Catalogos configurables por empresa (RF-100, #41) --------------------
#
# Van bajo `/audits/` y no en un router propio porque son la configuracion del
# registro de mejora: separarlos daria un modulo de una tabla y media cuyo
# unico lector vive aca.


@router.get(
    "/catalogos/severidades",
    response_model=list[SeveridadRead],
    tags=["catalogos-de-mejora"],
    summary="Escala de severidad de la empresa",
    description=(
        "Los niveles con que esta empresa clasifica sus hallazgos, de mas leve "
        "a mas grave. `days_to_close` en `null` significa que **no declaro "
        "plazo**: la fecha limite se sigue pidiendo a mano."
    ),
)
def list_severidades(
    solo_activas: bool = True,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    if solo_activas:
        return svc_catalogos.niveles_activos(db, tenant_id)
    return crud_severidad.get_multi(db, skip=0, limit=200)


@router.post(
    "/catalogos/severidades",
    response_model=SeveridadRead,
    status_code=status.HTTP_201_CREATED,
    tags=["catalogos-de-mejora"],
    summary="Agregar un nivel de severidad",
    description=(
        "El `code` es el valor que se guarda en el hallazgo, asi que tiene que "
        "ser uno de los que admite el CHECK de la columna mientras ese CHECK "
        "siga vigente. Lo que la empresa configura libremente es la etiqueta, "
        "el orden y el plazo."
    ),
)
def create_severidad(
    data: SeveridadCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_severidad.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch(
    "/catalogos/severidades/{severidad_id}",
    response_model=SeveridadRead,
    tags=["catalogos-de-mejora"],
    summary="Renombrar, reordenar o fijarle plazo a un nivel",
    description=(
        "Cambiar el plazo **no mueve las fechas limite ya calculadas**: la de "
        "un hallazgo se fijo con el compromiso vigente el dia que se registro, "
        "y recalcularla hacia atras reescribiria un plazo que alguien acordo."
    ),
)
def update_severidad(
    severidad_id: UUID,
    data: SeveridadUpdate,
    db: Session = Depends(get_tenant_db),
):
    obj = obtener_o_404(
        crud_severidad, db, severidad_id, recurso="Nivel de severidad"
    )
    obj = crud_severidad.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete(
    "/catalogos/severidades/{severidad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["catalogos-de-mejora"],
    summary="Retirar un nivel de severidad",
    description=(
        "Los hallazgos ya registrados con ese nivel **no se tocan**: su "
        "severidad es parte de lo que se decidio en su momento. Lo que cambia "
        "es que no se pueden registrar nuevos."
    ),
)
def delete_severidad(severidad_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_severidad, db, severidad_id, recurso="Nivel de severidad")


@router.get(
    "/catalogos/metodologias",
    response_model=list[MetodologiaRead],
    tags=["catalogos-de-mejora"],
    summary="Metodologias de analisis de causa de la empresa",
    description=(
        "`shape` dice que datos exige cada una: `cinco_porques` las respuestas "
        "encadenadas, `espina_pescado` las categorias, `texto_libre` ninguna en "
        "particular. El nombre lo elige la empresa; la forma no."
    ),
)
def list_metodologias(
    respuesta: Response,
    pagina: Pagina = Depends(paginacion),
    db: Session = Depends(get_tenant_db),
):
    return recortar(
        respuesta,
        crud_metodologia.get_multi(db, skip=pagina.skip, limit=pagina.pedir),
        pagina,
    )


@router.post(
    "/catalogos/metodologias",
    response_model=MetodologiaRead,
    status_code=status.HTTP_201_CREATED,
    tags=["catalogos-de-mejora"],
    summary="Agregar una metodologia",
    description=(
        "`shape` tiene que ser una de las tres formas que el sistema sabe "
        "pedir. El nombre es libre: una empresa llama a su metodologia como "
        "quiera, pero no puede inventar una forma para la que no hay ni "
        "formulario ni manera de leer las respuestas."
    ),
)
def create_metodologia(
    data: MetodologiaCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_metodologia.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch(
    "/catalogos/metodologias/{metodologia_id}",
    response_model=MetodologiaRead,
    tags=["catalogos-de-mejora"],
    summary="Editar una metodologia",
    description=(
        "Los hallazgos ya analizados con ella conservan su vinculo: cambiarle "
        "el nombre no reescribe con que se analizaron."
    ),
)
def update_metodologia(
    metodologia_id: UUID,
    data: MetodologiaUpdate,
    db: Session = Depends(get_tenant_db),
):
    obj = obtener_o_404(
        crud_metodologia, db, metodologia_id, recurso="Metodologia"
    )
    obj = crud_metodologia.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete(
    "/catalogos/metodologias/{metodologia_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["catalogos-de-mejora"],
    summary="Retirar una metodologia",
    description=(
        "Deja de ofrecerse para analisis nuevos. Los hallazgos que ya la usan "
        "siguen apuntandola: es parte de como se llego a su causa raiz."
    ),
)
def delete_metodologia(metodologia_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_metodologia, db, metodologia_id, recurso="Metodologia")


@router.get(
    "/catalogos/severidades/{severidad_id}",
    response_model=SeveridadRead,
    tags=["catalogos-de-mejora"],
    summary="Ver un nivel de severidad",
    description=(
        "Incluye los inactivos: un hallazgo antiguo puede apuntar a un nivel "
        "que la empresa ya no usa, y su ficha tiene que poder mostrarlo."
    ),
)
def get_severidad(severidad_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(
        crud_severidad, db, severidad_id, recurso="Nivel de severidad"
    )


@router.get(
    "/catalogos/metodologias/{metodologia_id}",
    response_model=MetodologiaRead,
    tags=["catalogos-de-mejora"],
    summary="Ver una metodologia",
    description=(
        "Incluye las inactivas, por el mismo motivo: el analisis de un hallazgo "
        "viejo nombra la metodologia con que se hizo."
    ),
)
def get_metodologia(metodologia_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(
        crud_metodologia, db, metodologia_id, recurso="Metodologia"
    )


# -- El informe de auditoria (RF-101, #42) --------------------------------


@router.get(
    "/{audit_id}/informe",
    response_model=InformeDeAuditoria,
    tags=["business-logic"],
    summary="Informe de auditoria con matriz por proceso",
    description=(
        "El informe completo (RF-101): resumen ejecutivo, **una fila por "
        "proceso auditado** y la tasa de cierre del ciclo anterior.\n\n"
        "**Todos los conteos se derivan al pedirlo**, no se guardan: un "
        "hallazgo que se cierra despues de emitir el informe cambia el numero "
        "la proxima vez que se abra. Lo unico persistido es lo que escribe el "
        "auditor — la clasificacion de cada proceso, su conclusion y la "
        "evidencia que tuvo a la vista.\n\n"
        "**Ojo con los `null`, que no son ceros.** `conformidad` viene vacia "
        "cuando no se evaluo ni una pregunta, y `tasa_de_cierre_del_ciclo_"
        "anterior` cuando no hay auditoria anterior, cuando la anterior no dejo "
        "hallazgos o cuando no esta cerrada. Un 0 % ahi se leeria como «no "
        "cerraron nada», que es una acusacion; `motivo_sin_tasa` dice cual de "
        "los tres casos es."
    ),
)
def informe_de_auditoria(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    try:
        return svc_informe.construir(db, audit_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from None


@router.get(
    "/{audit_id}/procesos",
    response_model=list[VeredictoDeProcesoRead],
    tags=["business-logic"],
    summary="Veredictos del auditor por proceso",
    description=(
        "Solo la parte **escrita** de la matriz. Los conteos y los hallazgos de "
        "cada proceso salen del informe, que los deriva."
    ),
)
def list_veredictos(audit_id: UUID, db: Session = Depends(get_tenant_db)):
    obtener_o_404(crud_audit, db, audit_id, recurso="Auditoria")
    return listar_por_padre(
        AuditProcessResult, db, audit_id, campo="audit_id"
    )


@router.post(
    "/{audit_id}/procesos",
    response_model=VeredictoDeProcesoRead,
    status_code=status.HTTP_201_CREATED,
    tags=["business-logic"],
    summary="Dejar el veredicto de un proceso",
    description=(
        "Un proceso tiene **un veredicto por auditoria y no mas**: dos seria una "
        "matriz que se contradice a si misma y el informe elegiria uno de los "
        "dos sin decirlo. Repetirlo responde 409.\n\n"
        "`no_auditado` es un veredicto valido y conviene usarlo: decirle al "
        "dueno de un proceso que no se lo miro es informacion, y una fila "
        "ausente se lee como un descuido del informe."
    ),
)
def create_veredicto(
    audit_id: UUID,
    data: VeredictoDeProcesoCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obtener_o_404(crud_audit, db, audit_id, recurso="Auditoria")
    # La clave foranea a `processes` no pasa por RLS: solo exige que la fila
    # exista, no que sea de esta empresa.
    validar_visible(crud_process, db, data.process_id, campo="process_id")

    ya_esta = db.scalar(
        select(AuditProcessResult).where(
            AuditProcessResult.audit_id == audit_id,
            AuditProcessResult.process_id == data.process_id,
            AuditProcessResult.deleted_at.is_(None),
        )
    )
    if ya_esta is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Ese proceso ya tiene veredicto en esta auditoria. Editalo en "
                "vez de agregar otro: dos veredictos sobre el mismo proceso "
                "dejarian la matriz contradiciendose."
            ),
        )

    # `audit_id` sale de la URL, no del cuerpo: mandarlo en el cuerpo dejaria
    # crear un veredicto bajo una auditoria y guardarlo en otra. Va antes del
    # create porque `CRUDBase.create` hace `flush` por dentro y la columna es
    # NOT NULL: ponerlo despues llega tarde y da 422 "falta un campo".
    obj = crud_veredicto_de_proceso.create(
        db,
        obj_in=VeredictoDeProcesoCreate(**data.model_dump(), audit_id=audit_id),
        tenant_id=tenant_id,
    )
    db.commit()
    return obj


@router.patch(
    "/{audit_id}/procesos/{veredicto_id}",
    response_model=VeredictoDeProcesoRead,
    tags=["business-logic"],
    summary="Corregir el veredicto de un proceso",
    description=(
        "El proceso no se cambia: mover un veredicto de un proceso a otro "
        "reescribiria lo que se dijo del primero. Se retira y se agrega."
    ),
)
def update_veredicto(
    audit_id: UUID,
    veredicto_id: UUID,
    data: VeredictoDeProcesoUpdate,
    db: Session = Depends(get_tenant_db),
):
    obtener_o_404(crud_audit, db, audit_id, recurso="Auditoria")
    obj = obtener_o_404(
        crud_veredicto_de_proceso, db, veredicto_id, recurso="Veredicto de proceso"
    )
    verificar_padre(obj, audit_id, campo="audit_id")
    obj = crud_veredicto_de_proceso.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete(
    "/{audit_id}/procesos/{veredicto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["business-logic"],
    summary="Retirar el veredicto de un proceso",
    description=(
        "El proceso vuelve a aparecer en la matriz como `no_auditado` si tiene "
        "preguntas, y desaparece de ella si no tiene ninguna."
    ),
)
def delete_veredicto(
    audit_id: UUID, veredicto_id: UUID, db: Session = Depends(get_tenant_db)
):
    obtener_o_404(crud_audit, db, audit_id, recurso="Auditoria")
    verificar_padre(
        obtener_o_404(
            crud_veredicto_de_proceso, db, veredicto_id, recurso="Veredicto de proceso"
        ),
        audit_id,
        campo="audit_id",
    )
    borrar_o_404(
        crud_veredicto_de_proceso, db, veredicto_id, recurso="Veredicto de proceso"
    )


@router.get(
    "/{audit_id}/procesos/{veredicto_id}",
    response_model=VeredictoDeProcesoRead,
    tags=["business-logic"],
    summary="Ver el veredicto de un proceso",
    description="La fila escrita por el auditor, sin los conteos derivados.",
)
def get_veredicto(
    audit_id: UUID, veredicto_id: UUID, db: Session = Depends(get_tenant_db)
):
    obtener_o_404(crud_audit, db, audit_id, recurso="Auditoria")
    return verificar_padre(
        obtener_o_404(
            crud_veredicto_de_proceso, db, veredicto_id, recurso="Veredicto de proceso"
        ),
        audit_id,
        campo="audit_id",
    )
