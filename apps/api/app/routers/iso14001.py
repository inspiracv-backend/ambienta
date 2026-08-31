from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..crud.iso14001 import crud_environmental_aspect, crud_regulated_equipment, crud_risk_opportunity
from ..deps import get_tenant_db, get_tenant_id
from ..crud.audit import crud_action_plan
from ..crud.compliance import crud_article_compliance
from ..crud.organization import crud_facility, crud_process, crud_user
from ..models.iso14001 import EquipmentOperator
from ._comun import CRUDAsociacion, borrar_o_404, obtener_o_404, validar_visible
from ..services import iso14001 as svc
from ..schemas.iso14001 import (
    AspectoSinTratar,
    Vencimientos,
    EvaluarSignificancia,
    ResultadoDeSignificancia,
    EquipmentOperatorUpdate,
    EquipmentOperatorRead,
    EquipmentOperatorCreateAnidado,
    EnvironmentalAspectCreate,
    EnvironmentalAspectRead,
    EnvironmentalAspectUpdate,
    RegulatedEquipmentCreate,
    RegulatedEquipmentRead,
    RegulatedEquipmentUpdate,
    RiskOpportunityCreate,
    RiskOpportunityRead,
    RiskOpportunityUpdate,
)

router = APIRouter(prefix="/iso14001", tags=["iso14001"])


def _validar_referencias(db: Session, data) -> None:
    """Toda clave foranea que venga del cuerpo, contra lo que RLS deja ver.

    **Las claves foraneas de Postgres no pasan por Row Level Security.**
    `fk_environmental_aspects_facility` solo exige que exista una fila en
    `facilities` con ese id: no mira el tenant. Medido contra la base: desde la
    empresa B, `SELECT` sobre la planta de la empresa A devuelve **cero filas**
    y el `INSERT` que la referencia **se acepta igual**.

    Son cuatro las que llegaban sin comprobar —`facility_id`, `process_id`,
    `article_compliance_id`, `environmental_aspect_id`, `action_plan_id`— y el
    dano no es solo una fila incoherente: distinguir "no existe" (falla la FK)
    de "existe pero es de otro" (pasa) es un oraculo para enumerar
    identificadores ajenos sin verlos nunca.

    Es exactamente la fuga que ya se midio y se corrigio en `POST /obligations/`.
    """
    for campo, crud in (
        ("facility_id", crud_facility),
        ("process_id", crud_process),
        ("article_compliance_id", crud_article_compliance),
        ("environmental_aspect_id", crud_environmental_aspect),
        ("action_plan_id", crud_action_plan),
        ("responsible_user_id", crud_user),
        ("owner_user_id", crud_user),
    ):
        valor = getattr(data, campo, None)
        if valor is not None:
            validar_visible(crud, db, valor, campo=campo)


@router.get("/aspects", response_model=list[EnvironmentalAspectRead])
def list_aspects(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_environmental_aspect.get_multi(db, skip=skip, limit=limit)


# **Esta ruta va antes que `/aspects/{aspect_id}` y no es cosmetico.** FastAPI
# resuelve por orden de declaracion: declarada despues, un GET a
# `/aspects/significant-untreated` cae en la ruta con parametro, intenta leer
# "significant-untreated" como UUID y responde **422**. Se midio: el endpoint
# existia en el OpenAPI y era inalcanzable por HTTP.
@router.get(
    "/aspects/significant-untreated",
    response_model=list[AspectoSinTratar],
    tags=["business-logic"],
    summary="Aspectos significativos sin riesgo asociado",
    description=(
        "El hallazgo mas comun de una auditoria de 14001: la empresa "
        "identifico el aspecto, lo declaro significativo, y ahi se detuvo. "
        "§6.1.4 pide que de los aspectos significativos salgan riesgos y "
        "oportunidades con su tratamiento.\n\n"
        "Van ordenados por total descendente: lo que mas pesa, primero."
    ),
)
def aspectos_significativos_sin_tratar(
    db: Session = Depends(get_tenant_db), tenant_id: UUID = Depends(get_tenant_id)
):
    return [
        AspectoSinTratar(
            id=a.id,
            activity=a.activity,
            aspect=a.aspect,
            total_score=a.total_score,
            facility_id=a.facility_id,
        )
        for a in svc.significativos_sin_riesgo(db, tenant_id)
    ]


@router.post("/aspects", response_model=EnvironmentalAspectRead, status_code=status.HTTP_201_CREATED)
def create_aspect(
    data: EnvironmentalAspectCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    _validar_referencias(db, data)
    obj = crud_environmental_aspect.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/aspects/{aspect_id}", response_model=EnvironmentalAspectRead)
def update_aspect(aspect_id: UUID, data: EnvironmentalAspectUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_environmental_aspect.get(db, aspect_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aspect not found")
    _validar_referencias(db, data)
    obj = crud_environmental_aspect.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/risks", response_model=list[RiskOpportunityRead])
def list_risks(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_risk_opportunity.get_multi(db, skip=skip, limit=limit)


@router.post("/risks", response_model=RiskOpportunityRead, status_code=status.HTTP_201_CREATED)
def create_risk(
    data: RiskOpportunityCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    _validar_referencias(db, data)
    obj = crud_risk_opportunity.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/risks/{risk_id}", response_model=RiskOpportunityRead)
def update_risk(risk_id: UUID, data: RiskOpportunityUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_risk_opportunity.get(db, risk_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    _validar_referencias(db, data)
    obj = crud_risk_opportunity.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/equipment", response_model=list[RegulatedEquipmentRead])
def list_equipment(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_regulated_equipment.get_multi(db, skip=skip, limit=limit)


# Antes que `/equipment/{equipment_id}`, por lo mismo que
# `significant-untreated`: FastAPI resuelve por orden de declaracion y al reves
# esta ruta responderia 422 intentando leer "expiring" como UUID.
@router.get(
    "/equipment/expiring",
    response_model=Vencimientos,
    tags=["business-logic"],
    summary="Inscripciones y certificaciones por vencer",
    description=(
        "Lo que hay que renovar antes de que caduque: la inscripcion del equipo "
        "ante la autoridad y la certificacion de quienes lo operan (#47).\n\n"
        "**Lo ya vencido viene incluido, no aparte.** Una lista de por vencer "
        "que deja fuera lo vencido es la unica que alguien mira, y esconde "
        "justamente lo urgente: `dias_restantes` sale negativo.\n\n"
        "Solo equipos en operacion. Uno detenido o dado de baja no necesita "
        "inscripcion vigente, y contarlo llenaria la lista de maquinas que "
        "nadie esta usando."
    ),
)
def equipos_por_vencer(
    dias: int = Query(default=svc.DIAS_DE_AVISO, ge=0, le=365),
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    return svc.vencimientos_proximos(db, tenant_id, dias=dias)


@router.post("/equipment", response_model=RegulatedEquipmentRead, status_code=status.HTTP_201_CREATED)
def create_equipment(
    data: RegulatedEquipmentCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    _validar_referencias(db, data)
    obj = crud_regulated_equipment.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/equipment/{equipment_id}", response_model=RegulatedEquipmentRead)
def update_equipment(equipment_id: UUID, data: RegulatedEquipmentUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_regulated_equipment.get(db, equipment_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    _validar_referencias(db, data)
    obj = crud_regulated_equipment.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/aspects/{aspect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_aspect(aspect_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_environmental_aspect, db, aspect_id, recurso="EnvironmentalAspect")


@router.delete("/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk(risk_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_risk_opportunity, db, risk_id, recurso="RiskOpportunity")


@router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment(equipment_id: UUID, db: Session = Depends(get_tenant_db)):
    """Da de baja un equipo regulado. Sus operadores certificados quedan
    asociados: la certificacion de una persona es suya, no del equipo."""
    borrar_o_404(crud_regulated_equipment, db, equipment_id, recurso="RegulatedEquipment")


@router.get("/aspects/{aspect_id}", response_model=EnvironmentalAspectRead)
def get_aspect(aspect_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_environmental_aspect, db, aspect_id, recurso="EnvironmentalAspect")


@router.get("/risks/{risk_id}", response_model=RiskOpportunityRead)
def get_risk(risk_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_risk_opportunity, db, risk_id, recurso="RiskOpportunity")


@router.get("/equipment/{equipment_id}", response_model=RegulatedEquipmentRead)
def get_equipment(equipment_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_regulated_equipment, db, equipment_id, recurso="RegulatedEquipment")


# ── Operadores certificados de un equipo (clave compuesta, anidada) ────────

crud_operador = CRUDAsociacion(EquipmentOperator, "equipment_id", "user_id")


@router.get("/equipment/{equipment_id}/operators", response_model=list[EquipmentOperatorRead])
def list_operators(equipment_id: UUID, db: Session = Depends(get_tenant_db)):
    obtener_o_404(crud_regulated_equipment, db, equipment_id, recurso="RegulatedEquipment")
    return crud_operador.listar(db, equipment_id)


@router.post("/equipment/{equipment_id}/operators/{user_id}", response_model=EquipmentOperatorRead, status_code=status.HTTP_201_CREATED)
def add_operator(
    equipment_id: UUID,
    user_id: UUID,
    data: EquipmentOperatorCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Acredita a una persona para operar el equipo."""
    obtener_o_404(crud_regulated_equipment, db, equipment_id, recurso="RegulatedEquipment")
    validar_visible(crud_user, db, user_id, campo="user_id")
    if crud_operador.obtener(db, equipment_id, user_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esa persona ya esta acreditada en el equipo.")
    obj = crud_operador.crear(db, padre_id=equipment_id, hijo_id=user_id, datos=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/equipment/{equipment_id}/operators/{user_id}", response_model=EquipmentOperatorRead)
def update_operator(equipment_id: UUID, user_id: UUID, data: EquipmentOperatorUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_operador.obtener(db, equipment_id, user_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    obj = crud_operador.actualizar(db, db_obj=obj, datos=data)
    db.commit()
    return obj


@router.delete("/equipment/{equipment_id}/operators/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_operator(equipment_id: UUID, user_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira la acreditacion. Borrado logico: haber estado certificado en un
    periodo es parte del historial que audita la norma."""
    if crud_operador.borrar(db, padre_id=equipment_id, hijo_id=user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    db.commit()


@router.get("/equipment/{equipment_id}/operators/{user_id}", response_model=EquipmentOperatorRead)
def get_operator(equipment_id: UUID, user_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_operador.obtener(db, equipment_id, user_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    return obj


# ── Significancia (#44) y su trazabilidad hacia riesgos (#49) ─────────────


@router.post(
    "/aspects/{aspect_id}/evaluate",
    response_model=ResultadoDeSignificancia,
    tags=["business-logic"],
    summary="Evaluar la significancia de un aspecto",
    description=(
        "Aplica los criterios de ISO 14001 §6.1.2 y guarda el total junto con "
        "el veredicto.\n\n"
        "**Los tres puntajes son obligatorios.** Con uno suelto no hay juicio "
        "que hacer, y aceptar la evaluacion a medias dejaria el aspecto marcado "
        "como no significativo por los criterios que faltan. Sin evaluar se "
        "queda en `pending`, que dice la verdad.\n\n"
        "Devuelve **por que** quedo asi: en una auditoria esa es la pregunta, y "
        "un aspecto de magnitud baja puede ser significativo igual porque hay "
        "un requisito legal aplicable."
    ),
)
def evaluar_significancia(
    aspect_id: UUID,
    datos: EvaluarSignificancia,
    db: Session = Depends(get_tenant_db),
):
    aspecto = obtener_o_404(
        crud_environmental_aspect, db, aspect_id, recurso="EnvironmentalAspect"
    )
    try:
        motivos = svc.evaluar_aspecto(
            db,
            aspecto,
            datos.frequency_score,
            datos.severity_score,
            datos.legal_score,
        )
    except svc.ErrorDeSignificancia as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
    db.commit()
    db.refresh(aspecto)
    return ResultadoDeSignificancia(
        aspect=EnvironmentalAspectRead.model_validate(aspecto), motivos=motivos
    )
