"""Departamentos de la empresa (RF-10 a RF-12).

Ruta plana y no anidada bajo `/facilities` porque `facility_id` es NULLABLE:
existen departamentos a nivel empresa —Legal, Finanzas— que no cuelgan de
ninguna planta y bajo `/facilities/{id}/departments` no tendrian direccion.

Las dos claves foraneas que se pueden editar se validan contra la sesion. No
es celo: las FK de Postgres no pasan por RLS, asi que sin esa comprobacion se
puede dejar un departamento apuntando a la planta de otra empresa.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..crud.organization import crud_department, crud_facility
from ..deps import get_tenant_db, get_tenant_id
from ..schemas.organization import DepartmentCreate, DepartmentRead, DepartmentUpdate
from ._comun import borrar_o_404, obtener_o_404, validar_sin_ciclo, validar_visible

router = APIRouter(prefix="/departments", tags=["departments"])


def _validar_referencias(
    db: Session,
    *,
    facility_id: UUID | None,
    parent_department_id: UUID | None,
    id_propio: UUID | None = None,
) -> None:
    """Las mismas comprobaciones en alta y en edicion.

    Estaban solo pensadas para el PATCH, pero un POST puede plantar la fila
    incoherente desde el principio: si la validacion vale en uno, vale en los
    dos.
    """
    validar_visible(crud_facility, db, facility_id, campo="facility_id")
    validar_visible(
        crud_department, db, parent_department_id, campo="parent_department_id"
    )
    validar_sin_ciclo(
        crud_department,
        db,
        id_propio=id_propio,
        id_padre=parent_department_id,
        campo="parent_department_id",
    )


@router.get("/", response_model=list[DepartmentRead])
def list_departments(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)
):
    return crud_department.get_multi(db, skip=skip, limit=limit)


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(department_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_department, db, department_id, recurso="Department")


@router.post("/", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    data: DepartmentCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    _validar_referencias(
        db,
        facility_id=data.facility_id,
        parent_department_id=data.parent_department_id,
    )
    obj = crud_department.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: UUID,
    data: DepartmentUpdate,
    db: Session = Depends(get_tenant_db),
):
    obj = obtener_o_404(crud_department, db, department_id, recurso="Department")
    _validar_referencias(
        db,
        facility_id=data.facility_id,
        parent_department_id=data.parent_department_id,
        id_propio=department_id,
    )
    obj = crud_department.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(department_id: UUID, db: Session = Depends(get_tenant_db)):
    """Da de baja un departamento.

    **No comprueba dependientes.** Seis tablas apuntan aca —`users`,
    `user_roles`, `tasks`, `article_compliance`, `processes` y el propio
    arbol— y el borrado logico no las toca: quedan usuarios y tareas asignados
    a un departamento al que la API responde 404. Es un pendiente conocido, no
    un descuido; resolverlo pide decidir antes que hacer con esos dependientes
    (reasignar, bloquear la baja, o dejarlos huerfanos a proposito).
    """
    borrar_o_404(crud_department, db, department_id, recurso="Department")
