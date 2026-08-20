"""Escribir el registro de actividades (RF-32, RNF-25).

## Por que esto no existia y hacia falta

`audit_log` estaba **vacia y nadie escribia en ella**: existia `GET
/system/audit-log` para leerla y ningun camino para llenarla. El historial que
se ve en pantalla vivia en el navegador y desaparecia al recargar.

Eso importa mas alla de la funcionalidad: **la rotacion mensual que pidio el
negocio no tiene sentido sobre una tabla vacia**, y quien la planeo creia que ya
se estaba grabando.

## La regla que evita un registro inutil

**Una accion que no cambio nada no se registra.** Guardar "actualizo la empresa"
cuando la persona abrio el formulario y guardo sin tocar nada llena la tabla de
ruido — y el ruido no es gratis: es lo que hace que despues nadie encuentre el
cambio que importa, y lo que degrada la base que justamente se quiere rotar.

Lo pidio el negocio con esas palabras: *"si el user no mete datos, no sale log
guardado"*.

## Que se guarda y que no

- `before_data` y `after_data` llevan **solo los campos que cambiaron**, no la
  fila entera. Una fila completa por cada edicion multiplica el tamano sin
  agregar informacion: lo que se audita es el cambio.
- **Nunca se guardan secretos.** `password_hash`, `clerk_id` y cualquier campo
  de credencial quedan fuera aunque hayan cambiado; el registro de auditoria se
  exporta y se comparte, y un hash filtrado ahi es un hash filtrado.

## La inmutabilidad es de la aplicacion, no de la base

`ambienta_app` —la conexion de la API— tiene solo `INSERT` y `SELECT`: no puede
editar ni borrar lo ya escrito. El dueno de la base **si** puede, y por eso una
tarea de mantenimiento puede archivar y purgar. La diferencia es deliberada: un
endpoint mal escrito no puede tapar sus huellas, y una rutina de mantenimiento
si puede hacer su trabajo.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.system import AuditLog

logger = logging.getLogger(__name__)

#: Los unicos valores que acepta `audit_log.action`, por CHECK en la base.
#:
#: **No es lo mismo que el vocabulario del frontend**, y la diferencia no es de
#: idioma: `packages/shared/src/schemas/audit-log.ts` declara doce acciones
#: —`creado`, `evaluado`, `asignado`, `comentado`…— y la base acepta estas
#: siete. Cuatro de las del frontend no tienen equivalente aca, y `login` y
#: `sync` no existen alla.
#:
#: Mientras sigan divergiendo, **enchufar el historial del frontend a la API
#: haria fallar la mayoria de las escrituras** contra el CHECK. Se expone la
#: lista para que nadie invente un verbo y lo descubra en produccion; cual de
#: los dos vocabularios gana es una decision pendiente del equipo.
ACCIONES = frozenset(
    {"create", "update", "delete", "approve", "login", "download", "sync"}
)

#: Traduccion del vocabulario del frontend al que acepta la base.
#:
#: Es una perdida de informacion consciente: `cerrado` y `reabierto` se vuelven
#: ambos `update`, y el matiz se guarda en `metadata`. Preferible a rechazar la
#: escritura, y preferible a ampliar el CHECK sin decidirlo.
ACCION_DESDE_EL_FRONTEND: dict[str, str] = {
    "creado": "create",
    "actualizado": "update",
    "eliminado": "delete",
    "exportado": "download",
    "estado_cambiado": "update",
    "evaluado": "update",
    "asignado": "update",
    "cerrado": "update",
    "reabierto": "update",
    "suspendido": "update",
    "reactivado": "update",
    "comentado": "update",
}

#: Campos que nunca entran al registro, hayan cambiado o no.
#:
#: El registro se exporta a JSON y se comparte con el cliente en una auditoria.
#: Un hash de contrasena ahi adentro deja de estar protegido por la base.
CAMPOS_SECRETOS = frozenset(
    {"password_hash", "clerk_id", "secret_reference", "api_key", "token"}
)


def diferencia(
    antes: dict[str, Any] | None, despues: dict[str, Any] | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Solo los campos que cambiaron, sin secretos.

    Devuelve `(antes, despues)` acotados a las claves cuyo valor difiere. Dos
    diccionarios vacios significan **que no cambio nada**, y quien llama tiene
    que tratar eso como "no hay nada que registrar".

    Comparar con `!=` y no con identidad: `1` y `1.0` son iguales para el
    negocio aunque sean objetos distintos, y registrar eso como un cambio seria
    ruido.
    """
    antes = antes or {}
    despues = despues or {}
    claves = (set(antes) | set(despues)) - CAMPOS_SECRETOS

    cambiaron = {k for k in claves if antes.get(k) != despues.get(k)}
    return (
        {k: antes[k] for k in cambiaron if k in antes},
        {k: despues[k] for k in cambiaron if k in despues},
    )


def registrar(
    db: Session,
    *,
    tenant_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    antes: dict[str, Any] | None = None,
    despues: dict[str, Any] | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog | None:
    """Anota una accion en el registro. Devuelve `None` si no habia nada que anotar.

    **No hace `commit`.** Se suma a la transaccion de quien llama, para que el
    registro y el cambio que describe entren o no entren juntos. Registrar por
    separado dejaria constancia de ediciones que fallaron.

    ## Cuando devuelve `None`

    Cuando se pasan `antes` y `despues` y **ningun campo cambio**. Es la regla
    del negocio —lo que no cambia no se registra— y se resuelve aca en vez de en
    cada router para que no dependa de que alguien se acuerde.

    Una creacion o un borrado no pasan por ese filtro: no tienen "antes" contra
    el cual comparar, y el hecho de haber ocurrido ya es la informacion.
    """
    if action not in ACCIONES:
        # Se falla temprano y con un mensaje que dice que hacer. Dejarlo pasar
        # lo convierte en un error de restriccion de Postgres a mitad del
        # commit, que se lee como un problema de la base y no del verbo.
        raise ValueError(
            f"Accion '{action}' no valida para el registro. La base acepta: "
            f"{', '.join(sorted(ACCIONES))}. Si venis del vocabulario del "
            f"frontend, traducila con ACCION_DESDE_EL_FRONTEND."
        )

    hubo_comparacion = antes is not None or despues is not None
    cambio_antes, cambio_despues = diferencia(antes, despues)

    if hubo_comparacion and not cambio_antes and not cambio_despues:
        # Abrir un formulario y guardar sin tocar nada no es un evento. Anotarlo
        # llena la tabla de ruido, y el ruido es lo que despues hace que nadie
        # encuentre el cambio que importa.
        return None

    entrada = AuditLog(
        tenant_id=tenant_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        before_data=cambio_antes or None,
        after_data=cambio_despues or None,
        reason=reason,
        metadata_=metadata or {},
    )
    db.add(entrada)
    return entrada
