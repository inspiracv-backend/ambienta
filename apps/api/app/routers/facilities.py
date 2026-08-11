from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.organization import crud_facility, crud_process
from ..deps import get_tenant_db, get_tenant_id
from ..crud.catalog import crud_facility_norm_assignment
from ..models.catalog import FacilityNormAssignment
from ..models.organization import FacilityProcess
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
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_tenant_db),
):
    return crud_facility.get_multi(db, skip=skip, limit=limit)


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
    obtener_o_404(crud_facility, db, facility_id, recurso="Facility")
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
