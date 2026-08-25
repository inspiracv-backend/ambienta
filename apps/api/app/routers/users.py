from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..crud.organization import crud_department, crud_user
from ..deps import exigir_permiso, get_tenant_db, get_tenant_id
from ..models.organization import Permission, UserPermission
from ..services.permisos import excepciones_del_usuario, permisos_de_roles
from ._comun import borrar_o_404, validar_visible
from ..schemas.organization import (
    PermisoEfectivo,
    PermisoIndividual,
    PermisosDelUsuario,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserRead])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_user.get_multi(db, skip=skip, limit=limit)


def _validar_departamento(db: Session, department_id: UUID | None) -> None:
    """Que el departamento sea de la propia empresa.

    **Las FK de Postgres no pasan por RLS.** `fk_users_department` solo exige
    que exista una fila en `departments` con ese id: no mira el tenant. Un
    `PATCH` con el departamento de otra empresa pasaba la restriccion y dejaba
    a la persona colgando de una estructura ajena.

    Y el dano no es solo la fila incoherente: es un **oraculo de existencia**.
    Quien prueba identificadores al azar distingue "no existe" de "existe pero
    es de otro", y con eso enumera identificadores ajenos sin verlos nunca. Por
    eso `validar_visible` responde 422 en los dos casos, deliberadamente.

    `processes.py` ya validaba esta misma columna; `users.py` no. Era el mismo
    agujero en el mismo campo, cerrado en un lado y abierto en el otro.
    """
    if department_id is not None:
        validar_visible(crud_department, db, department_id, campo="department_id")


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_user.get(db, user_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return obj


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    _validar_departamento(db, data.department_id)
    obj = crud_user.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: UUID, data: UserUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_user.get(db, user_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _validar_departamento(db, data.department_id)
    obj = crud_user.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, db: Session = Depends(get_tenant_db)):
    """Saca a la persona de la empresa.

    Distinto de `status`: bloquear o deshabilitar es suspender —la persona
    sigue en la nomina y se puede revertir—, mientras que esto la retira. Su
    rastro en el registro de auditoria se conserva, que es lo que impide
    borrar la fila de verdad.
    """
    borrar_o_404(crud_user, db, user_id, recurso="User")


# ── Permisos (RF-08, RF-12) ───────────────────────────────────────────────
#
# `user_permissions` existia como tabla desde `db/05_user_permissions.sql` y
# no tenia API, asi que `users.updatePermisos` del frontend no podia llegar a
# la base. Esto lo destraba.
#
# Administrar permisos exige `role.manage` —"Administrar roles y permisos" en
# el catalogo sembrado—: quien puede cambiar lo que otros pueden hacer necesita
# permiso explicito para eso, o cualquiera se concede lo que quiera.
#
# El codigo tiene que existir en `permissions`. La primera version de esto usaba
# `usuarios.permisos`, que **no esta en el catalogo**: con Clerk configurado
# `tiene_permiso` habria devuelto siempre false y nadie habria podido
# administrar nada. Un permiso inventado no falla al escribirlo, falla al
# usarlo, y en modo desarrollo ni siquiera se nota porque la guarda no verifica.


@router.get("/{user_id}/permissions", response_model=PermisosDelUsuario)
def get_user_permissions(user_id: UUID, db: Session = Depends(get_tenant_db)):
    """Que puede hacer esta persona, y de donde le viene cada permiso.

    Leer no exige `role.manage`: ver los permisos de alguien de la misma
    empresa es informacion de trabajo, y RLS ya acota la consulta a la empresa
    de la sesion.
    """
    if not crud_user.get(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    desde_rol = permisos_de_roles(db, user_id)
    concedidas, denegadas = excepciones_del_usuario(db, user_id)
    efectivos = (desde_rol | concedidas) - denegadas

    catalogo = {p.code: p for p in db.scalars(select(Permission)).all()}
    permisos = [
        PermisoEfectivo(
            codigo=codigo,
            modulo=catalogo[codigo].module if codigo in catalogo else "",
            descripcion=catalogo[codigo].description if codigo in catalogo else "",
            # Individual gana como etiqueta cuando viene de los dos lados: es
            # el que hay que tocar para revertirlo.
            origen="individual" if codigo in concedidas else "rol",
        )
        for codigo in sorted(efectivos)
    ]
    return PermisosDelUsuario(
        user_id=user_id, permisos=permisos, denegados=sorted(denegadas)
    )


@router.put(
    "/{user_id}/permissions/{codigo}",
    response_model=PermisosDelUsuario,
    tags=["business-logic"],
)
def set_user_permission(
    user_id: UUID,
    codigo: str,
    data: PermisoIndividual,
    tenant_id: UUID = Depends(get_tenant_id),
    _: CurrentUser = Depends(exigir_permiso("role.manage")),
    db: Session = Depends(get_tenant_db),
):
    """Concede o deniega un permiso a esta persona, por encima de su rol.

    Es `PUT` y no `PATCH` porque la operacion es idempotente: fijar el mismo
    permiso al mismo valor dos veces deja el mismo estado.

    **Denegar no es lo mismo que no conceder.** Una denegacion explicita gana
    sobre lo que otorgue cualquier rol, y es la unica forma de quitarle un
    permiso a alguien sin sacarlo del rol ni inventar un rol de excepcion.
    """
    if not crud_user.get(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    permiso = db.scalar(select(Permission).where(Permission.code == codigo))
    if permiso is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el permiso '{codigo}'.",
        )

    fila = db.get(UserPermission, (user_id, permiso.id))
    if fila is None:
        fila = UserPermission(user_id=user_id, permission_id=permiso.id, tenant_id=tenant_id)
        db.add(fila)
    fila.granted = data.granted
    fila.reason = data.reason
    db.commit()

    # Se relee despues del commit a proposito: devolver el conjunto entero
    # evita que la pantalla lo recalcule por su cuenta y se desincronice.
    return get_user_permissions(user_id, db)


@router.delete(
    "/{user_id}/permissions/{codigo}",
    response_model=PermisosDelUsuario,
    tags=["business-logic"],
)
def clear_user_permission(
    user_id: UUID,
    codigo: str,
    _: CurrentUser = Depends(exigir_permiso("role.manage")),
    db: Session = Depends(get_tenant_db),
):
    """Quita la excepcion individual y devuelve a la persona a lo que da su rol.

    No es lo mismo que denegar: denegar deja una fila que dice "este no, aunque
    el rol lo de". Esto borra la excepcion, de los dos signos.
    """
    permiso = db.scalar(select(Permission).where(Permission.code == codigo))
    if permiso is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el permiso '{codigo}'.",
        )

    fila = db.get(UserPermission, (user_id, permiso.id))
    if fila is not None:
        db.delete(fila)
        db.commit()
    return get_user_permissions(user_id, db)
