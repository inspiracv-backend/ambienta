"""Que el registro de actividades se escriba solo (RF-32, RNF-25).

## Por que no se enchufa router por router

`registrar()` existia y **nadie la llamaba**: `audit_log` tenia cero filas. La
salida obvia era agregar la llamada en cada endpoint que escribe. Son mas de
sesenta escrituras repartidas en dieciocho routers, y ese enfoque tiene un modo
de fallo conocido en este repo: *basta olvidarlo en uno*. Un recurso sin
auditar no se ve en ninguna pantalla y no rompe ninguna prueba — simplemente no
deja rastro, y eso se descubre el dia que hay que reconstruir quien cambio que.

Por eso se engancha **donde ya pasan todas las escrituras**: el `flush` de la
sesion. Lo que la ORM esta por mandar a la base es exactamente lo que hay que
auditar, sin que nadie tenga que acordarse.

## Lo que no cubre, dicho explicito

- **SQL crudo.** Lo que no pasa por la ORM la ORM no lo ve. Hoy eso es
  `guest_credentials`, que registra su propio evento de `login` a mano.
- **La sesion del webhook y las tareas.** El observador solo actua cuando la
  sesion trae contexto de request, que lo pone `get_tenant_db`. Una tarea de
  mantenimiento no tiene actor que anotar, y anotar `actor_user_id = NULL` en
  masa ensucia mas de lo que aporta.

Las dos son limitaciones reales. Estan aca escritas para que nadie lea "se
audita todo" y lo cite como un hecho.

## Un flush no es un commit

El registro se **suma a la misma transaccion** que el cambio que describe. Si
el request revienta despues, se van los dos juntos. Registrar aparte dejaria
constancia de ediciones que nunca ocurrieron, que es peor que no registrar.
"""
from __future__ import annotations

import datetime as dt
import decimal
import logging
import uuid
from typing import Any

from sqlalchemy import event, inspect, select
from sqlalchemy.dialects.postgresql import UUID as UUID_SQL
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ClauseElement

from ..models.organization import User
from ..models.system import AuditLog
from .auditoria import CAMPOS_SECRETOS, registrar

logger = logging.getLogger(__name__)

#: Clave donde `get_tenant_db` deja quien hace el request.
CONTEXTO = "auditoria"

#: Columnas que no son el cambio, sino la contabilidad de la fila.
#:
#: `created_at`/`updated_at` los pone la base en cada escritura: incluirlos
#: haria que **toda** actualizacion pareciera haber cambiado algo, y con eso se
#: cae la regla de "si no cambio nada, no se registra". `tenant_id` es constante
#: dentro del registro, que ya lleva el suyo.
CAMPOS_DE_CONTABILIDAD = frozenset(
    {"created_at", "updated_at", "created_by", "updated_by", "tenant_id"}
)

#: Tablas que no se auditan.
#:
#: `notifications` queda fuera porque las escribe el sistema, no una persona:
#: son miles de filas cuyo autor siempre es el mismo, y auditarlas convierte el
#: registro de cambios en un registro de trafico.
#:
#: `audit_log` esta en la lista **por defensa, no porque hoy haga falta**, y
#: conviene decirlo asi: se comprobo quitando el filtro entero y ninguna prueba
#: cambia. Las filas que agrega `registrar()` entran a la sesion *despues* de
#: que este observador fotografio `db.new`, y en el flush siguiente ya estan
#: persistidas. El filtro solo actuaria si alguien empezara a crear filas de
#: auditoria por otro camino. **Ninguna prueba lo cubre.**
TABLAS_SIN_AUDITORIA = frozenset({"audit_log", "notifications"})


def _json(valor: Any) -> Any:
    """Deja el valor en algo que JSONB acepte.

    `before_data` y `after_data` son JSONB: un UUID o un `datetime` crudo hacen
    reventar el `INSERT` a mitad del commit, y el error se lee como un problema
    de la base y no del serializador.
    """
    if isinstance(valor, ClauseElement):
        # El valor todavia no existe: es SQL que la base va a evaluar, como el
        # `now()` con que `remove()` marca la baja. **No se puede resolver aca
        # sin ir a la base**, y `bool()` sobre una expresion SQL ni siquiera
        # esta definido — es como reventaba antes de esta rama. Se guarda la
        # expresion, que dice la verdad: lo puso el servidor de datos.
        return f"<sql: {valor}>"
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, (uuid.UUID, dt.date, dt.datetime, dt.time)):
        return str(valor)
    if isinstance(valor, decimal.Decimal):
        # Como texto y no como float: el float redondea, y estos son montos y
        # mediciones. Un registro de auditoria que altera el numero que audita
        # no sirve para nada.
        return str(valor)
    if isinstance(valor, (list, tuple, set)):
        return [_json(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): _json(v) for k, v in valor.items()}
    return str(valor)


def _campos_auditables(obj: Any) -> list[str]:
    """Las columnas del modelo, menos la contabilidad y menos los secretos."""
    return [
        attr.key
        for attr in inspect(obj).mapper.column_attrs
        if attr.key not in CAMPOS_DE_CONTABILIDAD and attr.key not in CAMPOS_SECRETOS
    ]


def _valores(obj: Any) -> dict[str, Any]:
    return {
        campo: _json(getattr(obj, campo, None)) for campo in _campos_auditables(obj)
    }


def _cambios(obj: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Lo que tenia y lo que tiene, solo de lo que se toco.

    Se lee del historial de la ORM y no comparando contra la base: la ORM ya
    sabe el valor anterior de cada atributo cargado, y volver a consultarlo
    seria una consulta por fila editada.
    """
    estado = inspect(obj)
    antes: dict[str, Any] = {}
    despues: dict[str, Any] = {}

    for campo in _campos_auditables(obj):
        historial = estado.attrs[campo].history
        if not historial.has_changes():
            continue
        if historial.deleted:
            antes[campo] = _json(historial.deleted[0])
        if historial.added:
            despues[campo] = _json(historial.added[0])

    return antes, despues


def _es_borrado_logico(obj: Any) -> bool:
    """Si esta edicion es en realidad una baja.

    Un borrado logico llega al `flush` como un `UPDATE` de `deleted_at`.
    Registrarlo como `update` esconderia la baja entre las ediciones, y es
    justo el evento que mas se busca en un registro de auditoria.
    """
    if not hasattr(obj, "deleted_at"):
        return False
    historial = inspect(obj).attrs["deleted_at"].history
    if not historial.has_changes() or not historial.added:
        return False
    # `is not None` y no `bool(...)`: el valor entrante es `func.now()`, una
    # expresion SQL, y evaluarla como booleano lanza TypeError.
    return historial.added[0] is not None


def _id_de(obj: Any) -> uuid.UUID | None:
    """El id de la fila, si es un UUID.

    `audit_log.entity_id` es `uuid`. Las tablas de union tienen clave compuesta
    y las de catalogo usan enteros: en esos casos el id no entra en la columna,
    y forzarlo seria un error de tipo a mitad del commit. Queda `NULL` y la
    identificacion la da `entity_type` mas los datos del cambio.
    """
    valor = getattr(obj, "id", None)
    return valor if isinstance(valor, uuid.UUID) else None


def _asegurar_id(obj: Any) -> None:
    """Le pone el UUID a una fila nueva **antes** de que se inserte.

    El id de estas tablas lo genera Postgres con `gen_random_uuid()`, asi que
    en `before_flush` todavia vale `None`: el registro de la creacion salia con
    `entity_id` vacio, y un "se creo una instalacion" sin decir cual no permite
    reconstruir nada. Es justo el evento en que mas importa saberlo.

    Adelantar la generacion a Python es equivalente —los dos son UUID v4 al
    azar— y no le quita nada a la base: el `DEFAULT` sigue ahi para todo lo que
    no pase por la ORM. Solo se toca la fila que **no tiene** id todavia.
    """
    columnas = inspect(obj).mapper.columns
    if "id" not in columnas or getattr(obj, "id", None) is not None:
        return
    if isinstance(columnas["id"].type, UUID_SQL):
        obj.id = uuid.uuid4()


def _actor(db: Session, contexto: dict[str, Any]) -> uuid.UUID | None:
    """El id interno de quien escribe. `None` si no se puede saber quien es.

    El JWT trae el id de Clerk, no el nuestro, asi que hay una consulta. Se
    resuelve **una sola vez por request** y solo cuando de verdad hay algo que
    registrar: un GET no paga nada.

    Devuelve `None` en desarrollo sin Clerk, donde la identidad no se conoce —
    el header solo declara la empresa. Inventar un actor ahi seria peor que no
    tenerlo: el registro diria que alguien hizo algo que no hizo.
    """
    if "actor_id" in contexto:
        return contexto["actor_id"]

    clerk_id = contexto.get("clerk_id")
    actor = None
    if clerk_id:
        actor = db.scalar(select(User.id).where(User.clerk_id == clerk_id))
        if actor is None:
            # Pasa cuando alguien entro por SSO y el webhook no llego a crear
            # su fila (en local no llega nunca). Se registra el evento igual,
            # sin actor: perder el rastro entero por no saber el nombre seria
            # cambiar un dato incompleto por ninguno.
            logger.warning(
                "Auditoria: no hay fila en users para el clerk_id %s; "
                "el evento se registra sin actor.",
                clerk_id,
            )

    contexto["actor_id"] = actor
    return actor


def _anotar(db: Session, contexto: dict[str, Any], obj: Any, accion: str) -> None:
    if accion == "create":
        antes, despues = None, _valores(obj)
    elif accion == "delete" and obj in db.deleted:
        # Un borrado en firme no tiene "despues". Se guarda lo que habia, que
        # es lo unico que queda de esa fila.
        antes, despues = _valores(obj), None
    else:
        antes, despues = _cambios(obj)

    registrar(
        db,
        tenant_id=contexto["tenant_id"],
        action=accion,
        entity_type=obj.__tablename__,
        entity_id=_id_de(obj),
        actor_user_id=_actor(db, contexto),
        antes=antes,
        despues=despues,
        metadata={
            clave: valor
            for clave, valor in (
                ("request_id", contexto.get("request_id")),
                ("ip", contexto.get("ip")),
                ("ruta", contexto.get("ruta")),
            )
            if valor
        },
    )


def _auditable(obj: Any) -> bool:
    return (
        not isinstance(obj, AuditLog)
        and getattr(obj, "__tablename__", None) not in TABLAS_SIN_AUDITORIA
    )


def observar_flush(db: Session, contexto_flush: Any, instancias: Any) -> None:
    """Anota en `audit_log` todo lo que esta sesion esta por escribir.

    Se engancha en `before_flush` y no en `after_flush` porque **es el ultimo
    momento en que la ORM todavia tiene el valor anterior** de cada atributo:
    despues del flush el historial ya se limpio y `before_data` saldria vacio.

    Agregar objetos aca es lo que `before_flush` permite explicitamente, y por
    eso las filas de auditoria entran en el mismo flush que el cambio.
    """
    contexto = db.info.get(CONTEXTO)
    if not contexto:
        return

    # Se fotografian las tres colecciones antes de agregar nada: `registrar()`
    # mete filas en `db.new`, y recorrer una coleccion que crece mientras se
    # recorre audita la auditoria sin fin.
    nuevos = [o for o in db.new if _auditable(o)]
    editados = [o for o in db.dirty if _auditable(o) and db.is_modified(o)]
    borrados = [o for o in db.deleted if _auditable(o)]

    for obj in nuevos:
        _asegurar_id(obj)
        _anotar(db, contexto, obj, "create")
    for obj in editados:
        _anotar(db, contexto, obj, "delete" if _es_borrado_logico(obj) else "update")
    for obj in borrados:
        _anotar(db, contexto, obj, "delete")


def instalar(fabrica_de_sesiones: Any) -> None:
    """Engancha el observador a una fabrica de sesiones.

    Se instala sobre `SessionLocal` y **no sobre `Session` a secas**: la sesion
    del webhook y la de las tareas usan otra fabrica, y engancharlo globalmente
    haria que un script de mantenimiento escribiera auditoria sin actor.
    """
    if not event.contains(fabrica_de_sesiones, "before_flush", observar_flush):
        event.listen(fabrica_de_sesiones, "before_flush", observar_flush)
