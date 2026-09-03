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
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..config import get_settings
from ..crud.organization import crud_tenant
from ..deps import declarar, exigir_admin_global, get_current_user, get_db
from ..models.organization import User
from ..schemas.organization import TenantCreate, TenantRead, TenantUpdate
from ..services import crm as svc_crm

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


def _es_admin_global(user: CurrentUser, db: Session) -> bool:
    """Predicado, no dependencia.

    `exigir_admin_global` protege una ruta entera; aca hace falta decidir por
    **campo**, porque el Admin Empresa si puede editar su empresa — solo no el
    RUT.

    Sin Clerk configurado no hay identidad que consultar y el modo desarrollo ya
    confia en quien llama, asi que se responde que si. La barrera vive donde
    importa, que es cualquier entorno con el proveedor puesto.
    """
    if not get_settings().clerk_configured:
        return True
    fila = db.scalar(select(User).where(User.clerk_id == user.user_id))
    return fila is not None and fila.user_type == "platform_admin"


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
    """Alta de una empresa cliente. Solo Admin Global.

    **Y con su pipeline comercial listo.** `db/22_crm.sql` siembra las etapas
    del CRM con un `CROSS JOIN tenants`, que corre una sola vez: las empresas
    dadas de alta despues de esa migracion quedaban con **cero etapas**, y eso
    no se ve como un error — el kanban se muestra vacio, igual que una empresa
    que todavia no vende, y el primer trato responde 409. Se siembra aca para
    que no dependa de cuando nacio la empresa.

    Se declara el tenant antes de sembrar porque `crm_stages` **si** lleva RLS:
    esta sesion es `get_db` —sin empresa declarada— y el `INSERT` no pasaria el
    `WITH CHECK` de la politica. Va en la **misma transaccion** que el alta: una
    empresa a medias, creada pero sin pipeline, es justo el estado que esto
    existe para evitar.
    """
    obj = crud_tenant.create(db, obj_in=data)
    declarar(db, obj.id)
    svc_crm.sembrar_etapas_por_defecto(db, obj.id)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{tenant_id}", response_model=TenantRead)
def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Editar la propia empresa. Una ajena responde 404, no 403.

    **El RUT es la excepcion y va aparte.** El resto de los campos los edita el
    Admin Empresa; el RUT solo el Admin Global, porque identifica legalmente a
    la empresa ante la autoridad y cambiarlo permitiria emitir declaraciones a
    nombre de otra. Decision del equipo, 13-ago-2026.
    """
    _propia_o_404(tenant_id, user)

    if data.rut_tax_id is not None and not _es_admin_global(user, db):
        # 403 y no 404: aca no se esta revelando nada. Quien llama ya demostro
        # que la empresa es suya; lo que se le niega es tocar **un campo**, y
        # decirselo con claridad evita que lo reintente creyendo que fallo otra
        # cosa.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el Admin Global puede cambiar el RUT de una empresa.",
        )

    obj = crud_tenant.get(db, tenant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    obj = crud_tenant.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj
