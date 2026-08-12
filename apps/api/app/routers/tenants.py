"""Empresas cliente.

Es el unico router que no puede apoyarse en `get_tenant_db`: `tenants` no
tiene `tenant_id` —es la tabla de empresas, no se referencia a si misma—, asi
que Row Level Security no lo cubre. Toda la proteccion tiene que ser explicita
aca, y por eso vale leerlo entero antes de tocarlo.

Regla: cada quien ve **su** empresa. Quien administra la cartera es el Admin
Global, y eso lo verifica `exigir_admin_global`.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..crud.organization import crud_tenant
from ..deps import exigir_admin_global, get_current_user, get_db
from ..schemas.organization import TenantCreate, TenantRead, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _propia_o_404(tenant_id: UUID, user: CurrentUser) -> None:
    """404 y no 403 a proposito: no se confirma que la empresa exista.

    Un 403 le diria a quien pregunta que ese identificador es real y ademas
    ajeno. El 404 no distingue entre "no existe" y "no es tuya", que es lo
    mismo que ve la API para cualquier recurso fuera de su alcance.
    """
    if str(tenant_id) != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )


@router.get("/", response_model=list[TenantRead])
def list_tenants(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """La empresa de la sesion.

    Devuelve una lista de un elemento en vez de un objeto para no romper a
    quien ya consume este endpoint como coleccion. Antes listaba **todas** las
    empresas del sistema sin pedir autenticacion.
    """
    obj = crud_tenant.get(db, UUID(user.tenant_id))
    return [obj] if obj else []


@router.get("/{tenant_id}", response_model=TenantRead)
def get_tenant(
    tenant_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _propia_o_404(tenant_id, user)
    obj = crud_tenant.get(db, tenant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return obj


@router.post("/", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: TenantCreate,
    _: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    """Alta de una empresa cliente. Solo Admin Global."""
    obj = crud_tenant.create(db, obj_in=data)
    db.commit()
    return obj


@router.patch("/{tenant_id}", response_model=TenantRead)
def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Editar la propia empresa. Una ajena responde 404, no 403."""
    _propia_o_404(tenant_id, user)
    obj = crud_tenant.get(db, tenant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    obj = crud_tenant.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj
