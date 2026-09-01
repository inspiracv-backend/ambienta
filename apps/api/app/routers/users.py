from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..crud.organization import crud_department, crud_user
from ..deps import (
    exigir_permiso,
    get_current_user,
    get_tenant_db,
    get_tenant_id,
    volver_a_declarar,
)
from ..models.organization import Permission, UserPermission
from ..services import usuarios as svc_usuarios
from ..services import invitacion_de_usuario as svc_invitacion
from ..services import registro_de_invitado as svc_registro
from ..services.clave_local import ClerkNoDisponible
from ..services.permisos import excepciones_del_usuario, permisos_de_roles
from ._paginacion import Pagina, paginacion, recortar
from ._comun import borrar_o_404, validar_visible
from ..schemas.organization import (
    InvitacionEnviada,
    InvitadoRegistrado,
    RegistrarInvitadoPermanente,
    PermisoEfectivo,
    PermisoIndividual,
    PermisosDelUsuario,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


def _rechazar_si_deja_sin_vuelta(
    db: Session, obj, tenant_id: UUID, actual: CurrentUser
) -> None:
    """409 y no 422: el cuerpo esta bien, lo que no corresponde es el efecto.

    Un 422 diria "corrige lo que mandaste", y no hay nada que corregir — la
    peticion es legitima y el dato es valido. Lo que falta es otra persona con
    permiso para administrar usuarios.
    """
    try:
        svc_usuarios.validar_desactivacion(
            db, obj, tenant_id, clerk_id=actual.user_id
        )
    except svc_usuarios.ErrorDeUsuarios as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None


@router.get("/", response_model=list[UserRead])
def list_users(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_user.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


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
def update_user(
    user_id: UUID,
    data: UserUpdate,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
    actual: CurrentUser = Depends(get_current_user),
):
    obj = crud_user.get(db, user_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _validar_departamento(db, data.department_id)
    # Se comprueba **antes** de escribir, y solo si el cambio apaga a alguien
    # que estaba encendido: guardar `disabled` sobre quien ya lo estaba no
    # desactiva a nadie, y rechazarlo convertiria una edicion inocua en un 409.
    if svc_usuarios.desactiva(obj.status, data.status):
        _rechazar_si_deja_sin_vuelta(db, obj, tenant_id, actual)
    obj = crud_user.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
    actual: CurrentUser = Depends(get_current_user),
):
    """Saca a la persona de la empresa.

    Distinto de `status`: bloquear o deshabilitar es suspender —la persona
    sigue en la nomina y se puede revertir—, mientras que esto la retira. Su
    rastro en el registro de auditoria se conserva, que es lo que impide
    borrar la fila de verdad.

    Rige la misma guarda que el `PATCH` que desactiva, y aca con mas razon:
    retirar es lo mas dificil de deshacer de los dos.
    """
    obj = crud_user.get(db, user_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _rechazar_si_deja_sin_vuelta(db, obj, tenant_id, actual)
    borrar_o_404(crud_user, db, user_id, recurso="User")


def _traducir_invitacion(exc: svc_invitacion.ErrorDeInvitacion) -> HTTPException:
    """409 cuando ya esta invitada; 422 cuando el estado no corresponde."""
    if isinstance(exc, svc_invitacion.YaInvitado):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


def _traducir_registro(exc: svc_registro.ErrorDeRegistro) -> HTTPException:
    """Cada negativa a su codigo.

    **409 cuando el cuerpo esta bien y el estado no corresponde** —la credencial
    ya revocada, el correo ya tomado—: son peticiones legitimas y no hay nada
    que corregir en lo que se mando. **422 cuando falta un dato**, que es lo
    unico que quien llama puede arreglar.
    """
    if isinstance(
        exc, (svc_registro.CredencialYaRevocada, svc_registro.CorreoYaRegistrado)
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


@router.post(
    "/desde-invitado",
    response_model=InvitadoRegistrado,
    status_code=status.HTTP_201_CREATED,
    tags=["business-logic"],
    summary="Registrar de forma permanente a un Cliente Invitado",
    description=(
        "RF-03: quien entro por el acceso de invitado y quiere quedarse, lo "
        "registra el Admin Empresa.\n\n"
        "**No es cambiarle el rol a un usuario que ya existe.** Un invitado no "
        "es una fila de `users`: vive en `guest_credentials` con su RUT y su "
        "clave, y es el segundo emisor de identidad del sistema. Registrarlo es "
        "**crear a la persona** y llevarse consigo lo que ya hizo.\n\n"
        "Pasan tres cosas, y las tres se informan en `efectos`: se crea la "
        "cuenta, **sus solicitudes pasan a ser suyas** —si no, entraria y no "
        "veria lo que ella misma abrio— y **se revoca su acceso de invitado**, "
        "porque el sentido de registrarse es dejar de serlo.\n\n"
        "El nombre y el correo salen de sus solicitudes; la credencial solo "
        "guarda el RUT. Si nunca abrio ninguna, hay que indicarlos."
    ),
)
def registrar_invitado_permanente(
    datos: RegistrarInvitadoPermanente,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    # `department_id` viene del cuerpo: las claves foraneas **no pasan por
    # RLS**, asi que sin esto una empresa podria colgar a su gente del
    # departamento de otra. La credencial la comprueba el servicio, que la lee
    # con la sesion del tenant.
    validar_visible(crud_department, db, datos.department_id, campo="department_id")

    try:
        usuario, efectos = svc_registro.registrar_permanente(
            db,
            tenant_id,
            datos.guest_credential_id,
            datos.department_id,
            full_name=datos.full_name,
            email=datos.email,
            user_type=datos.user_type,
        )
    except svc_registro.ErrorDeRegistro as exc:
        raise _traducir_registro(exc) from None

    db.commit()
    db.refresh(usuario)
    return InvitadoRegistrado(user=UserRead.model_validate(usuario), efectos=efectos)


@router.post(
    "/{user_id}/invitacion",
    response_model=InvitacionEnviada,
    tags=["business-logic"],
    summary="Invitar por correo a una persona de la empresa",
    description=(
        "RF-03: el Admin Empresa registra a la persona y le manda la "
        "invitacion para que se cree la cuenta.\n\n"
        "**La emite Clerk, no nosotros.** La identidad la administra Clerk "
        "(ADR-006) y el signup publico se cierra, asi que la invitacion de "
        "Clerk **es** el mecanismo: un enlace de un solo uso ligado a ese "
        "correo, desde un remitente ya verificado.\n\n"
        "**Lleva el `tenant_id` en `public_metadata`.** Sin eso la persona "
        "acepta, entra y recibe `403 sesion_sin_empresa` en todo el sistema: "
        "el claim de empresa sale de ahi. Clerk lo copia al usuario al aceptar, "
        "asi que es el unico momento de dejarlo puesto sin tocar su consola.\n\n"
        "Solo se invita a quien **todavia no tiene acceso**. A alguien activo le "
        "mandaria un enlace que no necesita; a alguien desactivado le devolveria "
        "el acceso sin pasar por la decision de reactivarlo.\n\n"
        "Responde **503** si falta `CLERK_SECRET_KEY`: no es un error de lo que "
        "se mando, sino que la API no puede administrar cuentas."
    ),
)
def invitar_usuario(
    user_id: UUID,
    db: Session = Depends(get_tenant_db),
):
    try:
        usuario, respuesta = svc_invitacion.invitar_por_id(db, user_id)
    except svc_invitacion.ErrorDeInvitacion as exc:
        raise _traducir_invitacion(exc) from None
    except ClerkNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from None

    return InvitacionEnviada(
        user_id=usuario.id,
        email=usuario.email,
        # El identificador que devuelve Clerk, para poder rastrear la invitacion
        # en su consola sin buscarla por correo.
        clerk_invitation_id=str(respuesta.get("id") or "") or None,
    )


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
    #
    # **Y hay que volver a declarar el tenant antes de releer.** El commit
    # cierra la transaccion, y con ella se va el `SET LOCAL` que declaraba la
    # empresa: la relectura corria sin tenant y RLS devolvia cero filas, asi
    # que este endpoint escribia la fila y respondia 404 "User not found".
    volver_a_declarar(db)
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
        # Mismo motivo que en el PUT: sin esto la relectura sale vacia y
        # borrar la excepcion respondia 404 con la fila ya borrada.
        volver_a_declarar(db)
    return get_user_permissions(user_id, db)
