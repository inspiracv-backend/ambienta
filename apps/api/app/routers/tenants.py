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
from ..deps import (
    CODIGO_PLATAFORMA_NO_EDITA,
    declarar,
    exigir_admin_global,
    get_current_user,
    get_db,
)
from ..models.organization import Tenant, User
from ..schemas.organization import AltaDeEmpresa, TenantCreate, TenantRead, TenantUpdate
from ..services import catalogos_de_mejora as svc_catalogos
from ..services import crm as svc_crm
from ..services import invitacion_de_usuario as svc_invitacion
from ..services import roles_de_sistema as svc_roles
from ..services.clave_local import ClerkNoDisponible

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


def _admin_global_verificado(user: CurrentUser, db: Session) -> bool:
    """Si quien llama es Admin Global **con identidad comprobada**.

    Distinto de `_es_admin_global`, que en modo desarrollo responde que si a
    todos. Para **ver o tocar otra empresa** eso no alcanza: sin Clerk no hay
    identidad, y abrir la cartera entera a quien mande una cabecera es lo que
    este router cerro el 10-ago.
    """
    if not get_settings().clerk_configured:
        return False
    # **Se declara la empresa de la sesion antes de buscar.** Estas rutas piden
    # `get_db`, que no declara ninguna, y `users` lleva RLS. Hoy funciona igual
    # porque `exigir_permiso_de_la_ruta` —montada en `main.py`— resuelve
    # `get_tenant_db` sobre la **misma** sesion y ya la declaro; pero eso es un
    # acoplamiento invisible: quitar la guarda de este router dejaria la busqueda
    # en cero filas y al Admin Global sin reconocer, sin ningun error.
    # `tenants` no lleva RLS, asi que declarar no le quita nada a lo que sigue.
    declarar(db, UUID(user.tenant_id))
    fila = db.scalar(select(User).where(User.clerk_id == user.user_id))
    return fila is not None and fila.user_type == "platform_admin"


def _es_admin_global(user: CurrentUser, db: Session) -> bool:
    """Predicado, no dependencia.

    `exigir_admin_global` protege una ruta entera; aca hace falta decidir por
    **campo**, porque el Admin Empresa si puede editar su empresa — solo no el
    RUT ni lo que decide la plataforma.

    Sin Clerk configurado no hay identidad que consultar y el modo desarrollo ya
    confia en quien llama, asi que se responde que si. La barrera vive donde
    importa, que es cualquier entorno con el proveedor puesto.
    """
    if not get_settings().clerk_configured:
        return True
    return _admin_global_verificado(user, db)


#: Lo que la plataforma decide sobre una empresa, y no la empresa sobre si
#: misma: el RUT (identifica legalmente a la empresa ante la autoridad) y el
#: estado de la cuenta.
CAMPOS_DE_PLATAFORMA: frozenset[str] = frozenset({"rut_tax_id", "status"})

#: Las claves de `settings` que salen del contrato, con el valor que rige cuando
#: no estan guardadas: el de `LIMITE_USUARIOS_POR_DEFECTO` en `packages/shared`
#: y ningun modulo, que es lo que muestra la pantalla. `logoUrl` es de la empresa.
AJUSTES_DE_PLATAFORMA: dict[str, object] = {"limiteUsuarios": 50, "modulosActivos": []}

#: Espejo de `MODULOS_PLATAFORMA` (`packages/shared/src/schemas/tenant.ts`).
#: `test_cartera_del_admin_global.py` lee ese archivo y exige que coincidan.
MODULOS_PLATAFORMA: frozenset[str] = frozenset({
    "matriz-legal", "obligaciones", "calendario", "auditorias", "no-conformidades",
    "catalogo-normativo", "gestores", "reportes", "notificaciones", "usuarios-roles",
    "chatbot",
})

_AUSENTE = object()


def _lo_que_ve_la_pantalla(clave: str, guardados: dict) -> object:
    """El valor de un ajuste de plataforma tal como lo muestra la web.

    `leerTenantSettings` **descarta** una clave guardada que no valida y la
    pantalla muestra el valor por defecto. Al guardar reenvia ese defecto, y
    compararlo contra lo guardado en bruto se leeria como un cambio que nadie
    pidio — un 403 al guardar el logo de una empresa con un dato viejo.
    """
    valor = guardados.get(clave, _AUSENTE)
    if clave == "limiteUsuarios":
        valido = isinstance(valor, int) and not isinstance(valor, bool) and valor > 0
    else:
        valido = isinstance(valor, list) and all(
            isinstance(m, str) and m in MODULOS_PLATAFORMA for m in valor
        )
    return valor if valido else AJUSTES_DE_PLATAFORMA[clave]


@router.get("/", response_model=list[TenantRead])
def list_tenants(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """La empresa de la sesion; **la cartera entera para el Admin Global**.

    Devuelve una lista de un elemento en vez de un objeto para no romper a
    quien ya consume este endpoint como coleccion. Antes listaba **todas** las
    empresas del sistema sin pedir autenticacion.

    Y hasta el 14-sep, con Clerk, **tambien al Admin Global le devolvia una
    sola**: la de la plataforma. La pantalla de gestion de empresas —su trabajo
    entero— se veia con una fila. Solo con identidad comprobada: en modo
    desarrollo sigue devolviendo la de la cabecera.
    """
    if _admin_global_verificado(user, db):
        return list(
            db.scalars(
                select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.legal_name)
            ).all()
        )
    obj = crud_tenant.get(db, UUID(user.tenant_id))
    return [obj] if obj else []


@router.get("/{tenant_id}", response_model=TenantRead)
def get_tenant(
    tenant_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _admin_global_verificado(user, db):
        _propia_o_404(tenant_id, user)
    obj = crud_tenant.get(db, tenant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return obj


@router.post("/", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: AltaDeEmpresa,
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

    **Y con los catalogos del registro de mejora** (RF-100), por exactamente el
    mismo motivo: `db/25_catalogos_de_mejora.sql` tambien siembra con un
    `CROSS JOIN tenants`. Sin esto, una empresa nueva no tendria ningun nivel de
    severidad activo y registrar un hallazgo respondera 409 — otra forma de
    quedar inservible sin que nada falle.

    **Y con sus cuatro roles** (`services/roles_de_sistema.py`). `db/09` los
    siembra con otro `CROSS JOIN tenants`, y en produccion —sin el seed de
    demo— esa migracion corre con cero empresas: toda empresa nacia sin roles y
    su administrador recibia 403 en todo.

    **Y con su administrador, si viene** (RF-03). Se crea con `admin_empresa` y
    se le manda la invitacion de Clerk dentro de la misma transaccion: si la
    invitacion no sale, **la empresa tampoco se crea**. Antes la pantalla hacia
    `POST /users/` aparte, con el id local inventado de la empresa, y con Clerk
    configurado la API lo ignoraba y usaba la empresa **de la sesion**.

    Se declara el tenant antes de sembrar porque `crm_stages` y los dos
    catalogos **si** llevan RLS: esta sesion es `get_db` —sin empresa
    declarada— y el `INSERT` no pasaria el `WITH CHECK` de la politica. Va en la
    **misma transaccion** que el alta: una empresa a medias, creada pero sin
    pipeline ni catalogos, es justo el estado que esto existe para evitar.
    """
    datos = TenantCreate(**data.model_dump(exclude={"administrador"}, exclude_unset=True))
    obj = crud_tenant.create(db, obj_in=datos)
    declarar(db, obj.id)
    svc_crm.sembrar_etapas_por_defecto(db, obj.id)
    svc_catalogos.sembrar_por_defecto(db, obj.id)
    svc_roles.sembrar_roles_de_sistema(db, obj.id)

    if data.administrador is not None:
        try:
            svc_invitacion.registrar_e_invitar(
                db,
                obj.id,
                full_name=data.administrador.full_name.strip(),
                email=data.administrador.email.strip(),
                user_type="tenant_admin",
                department_id=None,
                role_code="admin_empresa",
            )
        except svc_invitacion.YaInvitado as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
        except svc_invitacion.ErrorDeInvitacion as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from None
        except ClerkNoDisponible as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from None

    db.refresh(obj)
    leida = TenantRead.model_validate(obj)
    db.commit()
    return leida


@router.patch("/{tenant_id}", response_model=TenantRead)
def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Editar la empresa. Una ajena responde 404, no 403 — salvo al Admin Global.

    Dos superficies con dueno distinto, y hasta el 14-sep no se distinguian:

    | quien | su empresa | otra empresa |
    |---|---|---|
    | Admin Empresa | todo **menos** RUT, estado, tope y modulos | 404 |
    | Admin Global | todo | **solo** RUT, estado, tope y modulos |

    **El RUT** identifica legalmente a la empresa ante la autoridad; cambiarlo
    permitiria emitir declaraciones a nombre de otra (decision del 13-ago). **El
    estado, el tope de usuarios y los modulos** salen del contrato: si la empresa
    los edita, el contrato no significa nada. Y el Admin Global no edita el
    contenido de un cliente (CLAUDE.md §4) — giro, direccion, logo son de ella.

    Se rechaza **cambiar** un campo, no mandarlo: la pantalla reenvia `settings`
    completo al guardar el logo, con el tope y los modulos que ya tenia.
    """
    propia = str(tenant_id) == user.tenant_id
    if not propia and not _admin_global_verificado(user, db):
        _propia_o_404(tenant_id, user)
    puede_lo_de_plataforma = _es_admin_global(user, db)

    obj = crud_tenant.get(db, tenant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    cambios = data.model_dump(exclude_unset=True)
    guardados = dict(obj.settings or {})
    nuevos = dict(cambios["settings"] or {}) if "settings" in cambios else None

    # Se compara contra lo guardado en los dos lados: **reenviar no es cambiar**,
    # ni un campo de la plataforma ni uno de la empresa.
    de_plataforma = {
        c for c in CAMPOS_DE_PLATAFORMA if c in cambios and cambios[c] != getattr(obj, c)
    }
    de_empresa = {
        c
        for c in cambios
        if c not in CAMPOS_DE_PLATAFORMA and c != "settings" and cambios[c] != getattr(obj, c)
    }
    if nuevos is not None:
        for clave in AJUSTES_DE_PLATAFORMA:
            if clave in nuevos and nuevos[clave] != _lo_que_ve_la_pantalla(clave, guardados):
                de_plataforma.add(clave)
            elif clave in guardados:
                # No mandarla, o reenviar lo que la pantalla ve, no la cambia: se
                # conserva lo guardado tal cual.
                nuevos[clave] = guardados[clave]
            else:
                # El valor por defecto reenviado no se escribe como un contrato.
                nuevos.pop(clave, None)

        for clave, valor in nuevos.items():
            if clave not in AJUSTES_DE_PLATAFORMA and guardados.get(clave, _AUSENTE) != valor:
                de_empresa.add("settings")
        for clave, valor in guardados.items():
            # **No mandar una clave no es borrarla.** La web omite las que no
            # sabe leer —un logo vacio, una clave vieja— y reemplazar `settings`
            # entero las borraba sin que nadie lo pidiera. Para quitar un logo se
            # manda `""`, que es un valor.
            nuevos.setdefault(clave, valor)

    if propia and de_plataforma and not puede_lo_de_plataforma:
        # 403 y no 404: la empresa es suya; lo que se le niega es **un campo**, y
        # decirselo evita que lo reintente creyendo que fallo otra cosa.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo el Admin Global puede cambiar "
                + ", ".join(sorted(de_plataforma))
                + " de una empresa."
            ),
        )
    if not propia and de_empresa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "codigo": CODIGO_PLATAFORMA_NO_EDITA,
                "mensaje": (
                    "El Admin Global administra el RUT, el estado, el tope y los "
                    "modulos de una empresa; no edita su contenido."
                ),
                "campos": sorted(de_empresa),
            },
        )

    if nuevos is not None:
        data = data.model_copy(update={"settings": nuevos})

    obj = crud_tenant.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj
