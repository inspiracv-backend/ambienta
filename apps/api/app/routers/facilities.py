from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crud.organization import crud_facility, crud_process
from ..deps import get_tenant_db, get_tenant_id
from ..crud.catalog import crud_facility_norm_assignment
from ..models.catalog import (
    FacilityNormAssignment,
    FacilityRetcReporting,
    RetcSystem,
)
from ..models.organization import FacilityProcess
from ._paginacion import Pagina, paginacion, recortar
from ._comun import (
    CRUDAsociacion,
    borrar_o_404,
    listar_por_padre,
    obtener_o_404,
    validar_visible,
    verificar_padre,
)
from ..schemas.catalog import (
    FacilityNormAssignmentCreate,
    FacilityNormAssignmentCreateAnidado,
    FacilityNormAssignmentRead,
    FacilityNormAssignmentUpdate,
    ReportabilidadRead,
    ReportabilidadUpsert,
)
from ..schemas.organization import (
    FacilityCreate,
    FacilityProcessCreateAnidado,
    FacilityProcessRead,
    FacilityProcessUpdate,
    FacilityRead,
    FacilityUpdate,
)

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("/", response_model=list[FacilityRead])
def list_facilities(
    respuesta: Response,
    pagina: Pagina = Depends(paginacion),
    db: Session = Depends(get_tenant_db),
):
    return recortar(respuesta, crud_facility.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.get("/{facility_id}", response_model=FacilityRead)
def get_facility(facility_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_facility.get(db, facility_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    return obj


@router.post("/", response_model=FacilityRead, status_code=status.HTTP_201_CREATED)
def create_facility(
    data: FacilityCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_facility.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{facility_id}", response_model=FacilityRead)
def update_facility(
    facility_id: UUID,
    data: FacilityUpdate,
    db: Session = Depends(get_tenant_db),
):
    obj = crud_facility.get(db, facility_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    obj = crud_facility.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(facility_id: UUID, db: Session = Depends(get_tenant_db)):
    """Da de baja una instalacion. Borrado logico: sus obligaciones y
    evaluaciones siguen referenciandola en el historial."""
    borrar_o_404(crud_facility, db, facility_id, recurso="Facility")


# ── Procesos que ocurren en una planta (clave compuesta, anidada) ──────────

crud_proceso_planta = CRUDAsociacion(FacilityProcess, "facility_id", "process_id")


@router.get("/{facility_id}/processes", response_model=list[FacilityProcessRead])
def list_facility_processes(facility_id: UUID, db: Session = Depends(get_tenant_db)):
    obtener_o_404(crud_facility, db, facility_id, recurso="Facility")
    return crud_proceso_planta.listar(db, facility_id)


@router.post("/{facility_id}/processes/{process_id}", response_model=FacilityProcessRead, status_code=status.HTTP_201_CREATED)
def add_facility_process(
    facility_id: UUID,
    process_id: UUID,
    data: FacilityProcessCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Declara que un proceso del mapa ocurre en esta planta."""
    obtener_o_404(crud_facility, db, facility_id, recurso="Facility")
    validar_visible(crud_process, db, process_id, campo="process_id")
    if crud_proceso_planta.obtener(db, facility_id, process_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese proceso ya esta declarado en la planta.")
    obj = crud_proceso_planta.crear(db, padre_id=facility_id, hijo_id=process_id, datos=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{facility_id}/processes/{process_id}", response_model=FacilityProcessRead)
def update_facility_process(facility_id: UUID, process_id: UUID, data: FacilityProcessUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_proceso_planta.obtener(db, facility_id, process_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FacilityProcess not found")
    obj = crud_proceso_planta.actualizar(db, db_obj=obj, datos=data)
    db.commit()
    return obj


@router.delete("/{facility_id}/processes/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_facility_process(facility_id: UUID, process_id: UUID, db: Session = Depends(get_tenant_db)):
    """El proceso deja de ocurrir en esta planta. Sus aspectos ambientales
    quedan: registran lo que paso mientras ocurria."""
    if crud_proceso_planta.borrar(db, padre_id=facility_id, hijo_id=process_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FacilityProcess not found")
    db.commit()


# ── Normas asignadas a una instalacion ─────────────────────────────────────

@router.get("/{facility_id}/norms", response_model=list[FacilityNormAssignmentRead])
def list_facility_norms(facility_id: UUID, db: Session = Depends(get_tenant_db)):
    """Que normas se le asignaron a esta instalacion, y en que estado."""
    return listar_por_padre(FacilityNormAssignment, db, facility_id, campo="facility_id")


@router.post("/{facility_id}/norms", response_model=FacilityNormAssignmentRead, status_code=status.HTTP_201_CREATED)
def create_facility_norm(
    facility_id: UUID,
    data: FacilityNormAssignmentCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Asigna una norma a la instalacion.

    `source` queda fijo en 'manual': lo que entra por este endpoint lo decidio
    una persona. Los valores 'rule', 'import' y 'ai_assisted' los pone quien
    los genera, y aceptarlos del cuerpo permitiria disfrazar una decision
    manual como si la hubiera sugerido el sistema.
    """
    obtener_o_404(crud_facility, db, facility_id, recurso="Facility")
    datos = data.model_dump()
    datos.update({"facility_id": facility_id, "source": "manual"})
    obj = crud_facility_norm_assignment.create(
        db, obj_in=FacilityNormAssignmentCreate(**datos), tenant_id=tenant_id
    )
    db.commit()
    return obj


@router.patch("/{facility_id}/norms/{asignacion_id}", response_model=FacilityNormAssignmentRead)
def update_facility_norm(
    facility_id: UUID,
    asignacion_id: UUID,
    data: FacilityNormAssignmentUpdate,
    db: Session = Depends(get_tenant_db),
):
    obj = obtener_o_404(crud_facility_norm_assignment, db, asignacion_id, recurso="FacilityNormAssignment")
    verificar_padre(obj, facility_id, campo="facility_id")
    obj = crud_facility_norm_assignment.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{facility_id}/norms/{asignacion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility_norm(facility_id: UUID, asignacion_id: UUID, db: Session = Depends(get_tenant_db)):
    """La norma deja de aplicar a esta instalacion. La norma en si no se toca:
    es catalogo compartido."""
    obj = obtener_o_404(crud_facility_norm_assignment, db, asignacion_id, recurso="FacilityNormAssignment")
    verificar_padre(obj, facility_id, campo="facility_id")
    borrar_o_404(crud_facility_norm_assignment, db, asignacion_id, recurso="FacilityNormAssignment")


@router.get("/{facility_id}/processes/{process_id}", response_model=FacilityProcessRead)
def get_facility_process(facility_id: UUID, process_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_proceso_planta.obtener(db, facility_id, process_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FacilityProcess not found")
    return obj


@router.get("/{facility_id}/norms/{asignacion_id}", response_model=FacilityNormAssignmentRead)
def get_facility_norm(facility_id: UUID, asignacion_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_facility_norm_assignment, db, asignacion_id, recurso="FacilityNormAssignment")
    return verificar_padre(obj, facility_id, campo="facility_id")


# ── Reportabilidad RETC de la instalacion (#102, ADR-004) ──────────────────
#
# Que sistemas del RETC le aplican a esta planta y con que estado. Hoy eso lo
# determina un especialista a mano cruzando articulos de la RCA con los
# portales que corresponden: dias de trabajo por instalacion nueva.
#
# Va anidado bajo la instalacion y no como recurso suelto porque **una
# reportabilidad no existe fuera de su planta**: es el mismo criterio que
# `/facilities/{id}/norms`.

ESTADOS = frozenset({"si", "condicional", "na", "no", "obligatorio"})


@router.get(
    "/{facility_id}/reportabilidad",
    response_model=list[ReportabilidadRead],
    summary="Que sistemas del RETC le aplican a esta instalacion",
    description=(
        "Devuelve **solo lo declarado**. Un sistema que no aparece no es lo "
        "mismo que uno en estado `no`: el primero **nadie lo ha mirado**, el "
        "segundo se revisó y se descartó. Confundirlos daria por cubierta una "
        "instalacion a medio configurar."
    ),
)
def list_reportabilidad(facility_id: UUID, db: Session = Depends(get_tenant_db)):
    obtener_o_404(crud_facility, db, facility_id, recurso="Facility")
    return listar_por_padre(
        FacilityRetcReporting, db, facility_id, campo="facility_id"
    )


@router.put(
    "/{facility_id}/reportabilidad/{system_id}",
    response_model=ReportabilidadRead,
    summary="Declarar el estado de un sistema para esta instalacion",
    description=(
        "**`PUT` y no `POST`**: hay como mucho una fila por instalacion y "
        "sistema —lo garantiza una unicidad en la base—, asi que volver a "
        "declararlo es corregir, no agregar. Con `POST` el segundo intento "
        "seria un 409 sobre algo que la persona esperaba poder cambiar.\n\n"
        "Un estado `condicional` **exige** decir de que depende."
    ),
)
def declarar_reportabilidad(
    facility_id: UUID,
    system_id: int,
    data: ReportabilidadUpsert,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obtener_o_404(crud_facility, db, facility_id, recurso="Facility")

    if data.estado not in ESTADOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Estado no valido. Opciones: {', '.join(sorted(ESTADOS))}.",
        )
    if data.estado == "condicional" and not (data.condicion or "").strip():
        # La base tambien lo exige por CHECK; se comprueba aca para responder
        # 422 con un motivo y no un error de restriccion a mitad del commit.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Un estado condicional tiene que decir de que depende: sin eso "
                "la decision no se puede revisar despues."
            ),
        )

    sistema = db.get(RetcSystem, system_id)
    if sistema is None or sistema.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="RetcSystem not found"
        )

    fila = db.scalar(
        select(FacilityRetcReporting).where(
            FacilityRetcReporting.facility_id == facility_id,
            FacilityRetcReporting.retc_system_id == system_id,
            FacilityRetcReporting.deleted_at.is_(None),
        )
    )

    if fila is None:
        fila = FacilityRetcReporting(
            tenant_id=tenant_id,
            facility_id=facility_id,
            retc_system_id=system_id,
        )
        db.add(fila)

    fila.estado = data.estado
    fila.condicion = data.condicion
    fila.variables = data.variables
    fila.responsable_id = data.responsable_id
    fila.notas = data.notas

    db.flush()
    db.refresh(fila)
    db.commit()
    return fila


@router.delete(
    "/{facility_id}/reportabilidad/{system_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar lo declarado para un sistema",
    description=(
        "Vuelve al estado **sin mirar**, que no es lo mismo que `no`. Sirve "
        "cuando la declaracion se hizo por error; para decir que el sistema no "
        "aplica, el estado correcto es `na` o `no`."
    ),
)
def borrar_reportabilidad(
    facility_id: UUID, system_id: int, db: Session = Depends(get_tenant_db)
):
    fila = db.scalar(
        select(FacilityRetcReporting).where(
            FacilityRetcReporting.facility_id == facility_id,
            FacilityRetcReporting.retc_system_id == system_id,
            FacilityRetcReporting.deleted_at.is_(None),
        )
    )
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FacilityRetcReporting not found",
        )
    fila.deleted_at = func.now()
    db.commit()
