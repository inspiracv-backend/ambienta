"""Mapa de procesos de la empresa (ISO 14001).

Es la entidad de la que cuelgan los aspectos ambientales: sin procesos no hay
donde registrar que impacto genera cada actividad.

`ProcessUpdate` no dejaba mover un proceso de departamento ni cambiarle el
padre, mientras que `DepartmentUpdate` si permitia lo equivalente. Era una
asimetria sin motivo: reorganizar el mapa de procesos es tan normal como
reorganizar el organigrama. Se abren, con las mismas validaciones.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..crud.organization import crud_department, crud_process, crud_user
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.organization import ProcessCreate, ProcessRead, ProcessUpdate
from ._comun import borrar_o_404, obtener_o_404, validar_sin_ciclo, validar_visible

router = APIRouter(prefix="/processes", tags=["processes"])


def _validar_referencias(
    db: Session,
    *,
    department_id: UUID | None,
    parent_process_id: UUID | None,
    responsible_user_id: UUID | None,
    id_propio: UUID | None = None,
) -> None:
    validar_visible(crud_department, db, department_id, campo="department_id")
    validar_visible(crud_user, db, responsible_user_id, campo="responsible_user_id")
    validar_visible(crud_process, db, parent_process_id, campo="parent_process_id")
    validar_sin_ciclo(
        crud_process,
        db,
        id_propio=id_propio,
        id_padre=parent_process_id,
        campo="parent_process_id",
    )


@router.get("/", response_model=list[ProcessRead])
def list_processes(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)
):
    return crud_process.get_multi(db, skip=skip, limit=limit)


@router.get("/{process_id}", response_model=ProcessRead)
def get_process(process_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_process, db, process_id, recurso="Process")


@router.post("/", response_model=ProcessRead, status_code=status.HTTP_201_CREATED)
def create_process(
    data: ProcessCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    _validar_referencias(
        db,
        department_id=data.department_id,
        parent_process_id=data.parent_process_id,
        responsible_user_id=data.responsible_user_id,
    )
    obj = crud_process.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{process_id}", response_model=ProcessRead)
def update_process(
    process_id: UUID, data: ProcessUpdate, db: Session = Depends(get_tenant_db)
):
    obj = obtener_o_404(crud_process, db, process_id, recurso="Process")
    _validar_referencias(
        db,
        department_id=getattr(data, "department_id", None),
        parent_process_id=getattr(data, "parent_process_id", None),
        responsible_user_id=data.responsible_user_id,
        id_propio=process_id,
    )
    obj = crud_process.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_process(process_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira un proceso del mapa.

    Sus aspectos ambientales quedan: son el registro de que impacto genero esa
    actividad mientras existio, y ese historial es lo que audita la norma.
    """
    borrar_o_404(crud_process, db, process_id, recurso="Process")
