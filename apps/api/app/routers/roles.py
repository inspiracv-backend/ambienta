"""Roles de la empresa y a quien se le asignan (#140, RF-08).

## Por que esto faltaba y por que importa

`user_roles` es **lo unico que decide que puede hacer cada persona**:
`permisos_efectivos` la lee, y la guarda de cada ruta consulta esa funcion. Y
hasta ahora no existia ni una sola ruta con `role` en su camino: la tabla se
poblaba en la migracion `09_roles_por_codigo.sql` y despues solo se podia tocar
con SQL a mano.

O sea que el RBAC funcionaba y **no se podia administrar**. La pantalla de
usuarios lo sabia: cambiar el rol mostraba un aviso diciendo que no se guardaba.

## Los dos "roles" que este repositorio tiene, y que no son el mismo

Conviene decirlo aca porque cuesta caro confundirlos:

| Campo | Valores | Para que sirve |
|---|---|---|
| `users.user_type` | `platform_admin`, `tenant_admin`, `internal`, `guest`, `manager` | **Que clase de cuenta es.** Decide si pertenece a un departamento (`ck_users_interno_con_departamento`), si es un invitado, si administra la plataforma |
| `roles.code` | `admin_empresa`, `encargado_ambiental`, `operador`, y los que cree la empresa | **Que puede hacer.** Es lo que se cruza con `role_permissions` |

`09_roles_por_codigo.sql` derivo el segundo del primero **una vez**, para que
nadie quedara sin permisos al encender la guarda. Despues son independientes:
cambiar uno no cambia el otro.

Este router administra **el segundo**, que es el que concede permisos. No toca
`user_type`: mezclarlos convertiria "dale permiso de administrar" en "conviertela
en administradora de la plataforma", y son cosas distintas.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud.organization import crud_role, crud_user
from ..deps import get_tenant_db, get_tenant_id
from ..models.organization import Role
from ..schemas.organization import RoleRead
from ..schemas.roles import RolesDelUsuario, ResultadoDeRoles, FijarRoles
from ..services import usuarios as svc
from ..services.permisos import roles_vigentes
from ._comun import validar_visible

router = APIRouter(tags=["roles"])


@router.get(
    "/roles/",
    response_model=list[RoleRead],
    summary="Roles de la empresa",
    description=(
        "Los roles con los que se puede administrar el acceso. Es lo que "
        "necesita un selector para poder asignar uno.\n\n"
        "**No es `users.user_type`.** Ese dice que clase de cuenta es una "
        "persona; esto dice que puede hacer. Ver el modulo para la diferencia."
    ),
)
def listar_roles(
    db: Session = Depends(get_tenant_db), tenant_id: UUID = Depends(get_tenant_id)
):
    return list(
        db.scalars(
            select(Role)
            .where(Role.tenant_id == tenant_id, Role.deleted_at.is_(None))
            .order_by(Role.code)
        ).all()
    )


@router.get(
    "/users/{user_id}/roles",
    response_model=RolesDelUsuario,
    summary="Roles vigentes de una persona",
    description=(
        "Solo los **vigentes**: un rol vencido no concede nada, y mostrarlo "
        "junto a los activos haria creer que la persona conserva permisos que "
        "ya se le retiraron."
    ),
)
def ver_roles(
    user_id: UUID,
    db: Session = Depends(get_tenant_db),
):
    usuario = crud_user.get(db, user_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    asignaciones = svc.roles_vigentes_de(db, user_id)
    return RolesDelUsuario(
        user_id=user_id,
        role_ids=[a.role_id for a in asignaciones],
        codigos=roles_vigentes(db, user_id),
    )


@router.put(
    "/users/{user_id}/roles",
    response_model=ResultadoDeRoles,
    summary="Fijar los roles de una persona",
    description=(
        "Deja a la persona **exactamente** con los roles indicados: los que "
        "sobran se retiran y los que faltan se asignan. Es un `PUT` y no un "
        "`POST` porque el cuerpo describe el estado final, no una adicion — "
        "con `POST` habria que ofrecer tambien un `DELETE` por rol y el estado "
        "resultante dependeria del orden de las llamadas.\n\n"
        "**Los roles retirados no se borran: se vencen.** La clave primaria es "
        "`(user_id, role_id)`, asi que volver a dar un rol reabre la misma "
        "fila; el historial de quien tuvo que rol vive en `audit_log`.\n\n"
        "Responde **409** si el cambio dejaria a la empresa sin ninguna persona "
        "activa que pueda administrar usuarios — el mismo bloqueo de #141 por "
        "otra puerta."
    ),
)
def fijar_roles(
    user_id: UUID,
    datos: FijarRoles,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    usuario = crud_user.get(db, user_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Los ids vienen del cuerpo: **las claves foraneas no pasan por RLS**, asi
    # que sin esto una empresa podria asignarle a su gente un rol de otra —y
    # con el, los permisos que esa otra empresa haya configurado.
    for role_id in datos.role_ids:
        validar_visible(crud_role, db, role_id, campo="role_ids")

    try:
        svc.validar_cambio_de_roles(db, usuario, tenant_id, datos.role_ids)
    except svc.ErrorDeUsuarios as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None

    efectos = svc.fijar_roles(db, usuario, tenant_id, datos.role_ids)
    db.commit()

    return ResultadoDeRoles(
        user_id=user_id,
        role_ids=[a.role_id for a in svc.roles_vigentes_de(db, user_id)],
        codigos=roles_vigentes(db, user_id),
        efectos=efectos,
    )
