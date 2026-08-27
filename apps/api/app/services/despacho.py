"""Toma los avisos encolados y los entrega (RF-41, #118).

## Por que la cola es Postgres y no Redis

ADR-005 dijo "Redis + ARQ o Celery". Se implementa distinto y conviene decir
por que, porque es apartarse de un ADR:

`notifications` **ya era una cola** antes de esta tarea. Tiene `status` con
`queued` por defecto, `scheduled_at`, `sent_at`, `provider_message_id`,
`dedupe_key` con indice unico y un indice parcial sobre los pendientes. Lo
unico que le faltaba era el estado de reintento, que agrega `db/19`.

Y hay una razon de correccion, no solo de ahorro: **la fila del aviso y el
hecho que lo causa se escriben en la misma transaccion**. Si la evaluacion de
la obligacion se deshace, el aviso se deshace con ella. Con la cola en Redis
son dos almacenes que pueden discrepar, y las dos formas de discrepar son
malas: un correo enviado por una obligacion que se revirtio, o una fila
`queued` que ningun trabajo va a atender porque el encolado fallo despues del
commit. Eso se resuelve con transacciones distribuidas o se acepta como riesgo;
tener la cola en la misma base lo hace desaparecer.

Lo que se pierde: rendimiento. Postgres aguanta ordenes de magnitud menos
trabajos por segundo que Redis. Para avisos de vencimiento —decenas al dia por
empresa— sobra. Si algun dia hay que mover miles por minuto, esto se cambia; el
`Transporte` y el contrato de estados sobreviven al cambio.

## Entrega al menos una vez, y acotada

El envio es un efecto externo: sale un correo. Entre "mandarlo" y "anotar que
salio" hay una ventana, y si el proceso muere ahi el aviso se reenvia. Se
prefiere **repetir un aviso antes que perderlo**: este sistema existe para que
un plazo no se pase, y un correo duplicado molesta mientras que uno que falta
no avisa a nadie.

Lo que si se hace es acotarlo. El intento se anota **antes** de enviar y se
confirma en el acto, asi que un proceso que muera en la ventana deja el
contador subido: se reintenta, pero no para siempre. Sin eso, un fallo que
mate al proceso en cada intento manda correos en bucle cerrado.

Anotar el intento antes cumple ademas de arriendo: al empujar
`next_attempt_at` al futuro, ningun otro despachador toma esa fila mientras se
esta enviando.

## Por que corre como dueno de la base

Los avisos son de todas las empresas y RLS —la unica barrera entre ellas
(CLAUDE.md §4)— hace que `ambienta_app` no vea mas que la suya. Esta tarea es
mantenimiento del sistema, como `rotar_auditoria`.

**Saltarse RLS significa que las comprobaciones que RLS hacia hay que hacerlas
a mano.** Concretamente `validar_destinatario()`: que la persona pertenezca a
la misma empresa que el aviso. Una fila mal escrita —o una FK que apunte fuera,
que en este esquema es posible porque las claves foraneas no pasan por RLS—
mandaria el aviso de una empresa al correo de otra. Con la sesion normal eso lo
impedia la base; aca no hay quien lo impida salvo este codigo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.notifications import Notification
from ..models.organization import User

logger = logging.getLogger("ambienta.despacho")

#: Cuantas veces se intenta antes de rendirse. Cinco intentos con la espera de
#: abajo cubren unas siete horas: si el proveedor no volvio en siete horas, el
#: problema no se arregla reintentando y alguien tiene que mirarlo.
MAX_INTENTOS = 5

#: Espera antes del siguiente intento, por numero de intento ya hecho. Crece
#: porque los fallos de un proveedor de correo son casi siempre cortes breves;
#: reintentar cada minuto contra un servicio caido es ruido que ademas gasta la
#: cuota. El ultimo valor se repite si hiciera falta.
ESPERAS = (
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=6),
)

#: Canales que no viajan a ningun lado. Una notificacion in-app **ya esta
#: entregada** cuando existe: el centro de notificaciones lee la tabla. Dejarla
#: en `queued` es una afirmacion falsa —dice "esperando envio" cuando nadie la
#: va a enviar— y esa clase de mentira es la que hace que despues nadie confie
#: en los estados.
SIN_TRANSPORTE = frozenset({"in_app"})


class ErrorDeEnvio(Exception):
    """El transporte no pudo entregar. Se reintenta."""


class ErrorPermanente(Exception):
    """No tiene sentido reintentar: la direccion no existe, el aviso esta mal.

    Se separa de `ErrorDeEnvio` porque reintentar cinco veces un correo a una
    direccion invalida no lo hace valido, y cada intento lo cobra el proveedor.
    """


class Transporte(Protocol):
    """Lo que sabe entregar un aviso por un canal externo.

    Es un protocolo y no una clase para que el despachador se pueda probar sin
    proveedor y sin red: las pruebas pasan uno que cuenta llamadas. El adaptador
    real de Resend (#122) encaja aca sin tocar este archivo.
    """

    def enviar(
        self, *, destino: str, asunto: str, cuerpo: str, contexto: dict
    ) -> str:
        """Entrega y devuelve el identificador del proveedor.

        Levanta `ErrorDeEnvio` si vale la pena reintentar, `ErrorPermanente` si
        no.
        """
        ...


@dataclass
class Resultado:
    entregados: int = 0
    fallidos: int = 0
    reintentables: int = 0
    rendidos: int = 0
    #: Correos que no se intentaron porque no hay proveedor configurado. Se
    #: cuentan aparte de `fallidos` a proposito: no fallo la entrega, falta la
    #: configuracion, y mezclarlos haria que un `.env` incompleto se leyera
    #: como un problema del proveedor.
    sin_proveedor: int = 0
    motivos: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        lineas = [
            f"entregados: {self.entregados}",
            f"a reintentar: {self.reintentables}",
            f"rendidos tras {MAX_INTENTOS} intentos: {self.rendidos}",
            f"rechazados sin reintento: {self.fallidos}",
            f"sin proveedor de correo: {self.sin_proveedor}",
        ]
        return "\n".join(lineas + [f"  - {m}" for m in self.motivos])


def _ahora() -> datetime:
    """El reloj de la aplicacion, a proposito.

    Aca si corresponde: se compara contra `scheduled_at`, que puede venir de
    cualquier lado, y el resultado se usa para decidir en Python. En
    `permisos.py` la comparacion vive dentro del SQL y por eso usa el reloj de
    la base; mezclar los criterios seria peor que elegir uno.
    """
    return datetime.now(timezone.utc)


def espera_tras(intentos: int) -> timedelta:
    """Cuanto esperar despues de `intentos` fallidos."""
    if intentos <= 0:
        return ESPERAS[0]
    return ESPERAS[min(intentos - 1, len(ESPERAS) - 1)]


def _vencimiento():
    """La fecha efectiva: el reintento si lo hay, si no la programada."""
    return func.coalesce(Notification.next_attempt_at, Notification.scheduled_at)


def tomar_uno(db: Session, *, excluir: list[UUID] | None = None) -> Notification | None:
    """Toma **un** aviso en exclusiva, o None si no hay nada que hacer.

    De a uno y no por lote, y la razon es concreta. Un lote tomado con
    `FOR UPDATE` parece mas eficiente, pero el primer `commit` del bucle
    —anotar el intento del primer aviso— **termina la transaccion y suelta los
    candados de todas las filas restantes**. A partir de ahi otro despachador
    las toma mientras este sigue recorriendo su lista en memoria, y los dos
    mandan el mismo correo. El lote solo seria seguro si nada dentro del bucle
    hiciera commit, y anotar el intento antes de enviar exige justamente eso.

    Con volumenes de decenas de avisos al dia por empresa, dos transacciones
    por aviso no se notan. Si algun dia se notan, la salida no es volver al
    lote suelto sino tomar el lote **y marcarlo entero** en la misma
    transaccion.

    `SKIP LOCKED` es lo que hace que un segundo despachador salte la fila
    tomada en vez de quedarse esperandola: sin el, se bloquearia hasta que el
    primero termine de hablar con el proveedor.
    """
    condiciones = [
        Notification.status == "queued",
        Notification.deleted_at.is_(None),
        _vencimiento() <= func.now(),
    ]
    if excluir:
        # Los saltados en esta corrida. Sin esto el bucle se traba: un aviso
        # que se salta sin tocarlo sigue cumpliendo la condicion y `tomar_uno`
        # lo devuelve otra vez, y otra, hasta agotar el limite sin avanzar.
        condiciones.append(Notification.id.not_in(excluir))

    return db.execute(
        select(Notification)
        .where(*condiciones)
        .order_by(_vencimiento())
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()


def validar_destinatario(db: Session, aviso: Notification) -> User:
    """La persona tiene que existir, estar activa y ser de **esta** empresa.

    La comprobacion de empresa no es redundante con la clave foranea: en este
    esquema **las claves foraneas no pasan por RLS**, y ademas aca corremos como
    dueno de la base, sin RLS. Es el unico punto donde se verifica que el aviso
    de una empresa no salga hacia el correo de otra.
    """
    persona = db.get(User, aviso.recipient_user_id) if aviso.recipient_user_id else None
    if persona is None:
        raise ErrorPermanente("el destinatario no existe")
    if persona.tenant_id != aviso.tenant_id:
        # Esto no deberia poder pasar. Si pasa, es un dato corrupto o un agujero
        # de aislamiento, y en los dos casos lo que NO hay que hacer es mandar
        # el correo.
        logger.error(
            "Aviso %s de la empresa %s apunta a un usuario de la empresa %s. No se envia.",
            aviso.id,
            aviso.tenant_id,
            persona.tenant_id,
        )
        raise ErrorPermanente("el destinatario es de otra empresa")
    if persona.deleted_at is not None:
        # `db.get()` devuelve la fila igual: la ORM no filtra el borrado logico
        # sola. Sin esta linea, dar de baja a alguien no lo saca de la lista de
        # correo, que es justamente lo que uno espera al darlo de baja.
        raise ErrorPermanente("el destinatario esta dado de baja")
    if persona.status != "active":
        raise ErrorPermanente(f"el destinatario esta {persona.status}")
    if not persona.email:
        raise ErrorPermanente("el destinatario no tiene correo")
    return persona


def _anotar_intento(db: Session, aviso: Notification) -> None:
    """Sube el contador y corre el reintento **antes** de enviar.

    Es lo que acota los duplicados y a la vez sirve de arriendo: mientras
    `next_attempt_at` este en el futuro, ningun otro despachador toma la fila.
    """
    aviso.attempts += 1
    aviso.next_attempt_at = _ahora() + espera_tras(aviso.attempts)
    db.flush()
    db.commit()


def _rendirse(db: Session, aviso: Notification, motivo: str) -> None:
    aviso.status = "failed"
    aviso.last_error = motivo[:2000]
    aviso.next_attempt_at = None
    db.flush()
    db.commit()


def _entregado(db: Session, aviso: Notification, id_proveedor: str | None) -> None:
    aviso.status = "delivered" if aviso.channel in SIN_TRANSPORTE else "sent"
    aviso.sent_at = _ahora()
    aviso.provider_message_id = id_proveedor
    aviso.last_error = None
    aviso.next_attempt_at = None
    db.flush()
    db.commit()


def despachar(
    db: Session, *, transporte: Transporte | None = None, limite: int = 50
) -> Resultado:
    """Entrega lo que este pendiente. Devuelve que paso con cada uno.

    `transporte` puede faltar: sin proveedor de correo configurado las
    notificaciones in-app igual se entregan, que es la mitad del producto. Los
    correos se quedan encolados **sin gastar intentos**, porque no es un fallo
    de entrega sino una configuracion que falta, y gastar los cinco intentos
    contra un proveedor ausente perderia los avisos el dia que se configure.
    """
    r = Resultado()
    saltados: list[UUID] = []

    for _ in range(limite):
        aviso = tomar_uno(db, excluir=saltados)
        if aviso is None:
            break

        if aviso.channel not in SIN_TRANSPORTE and transporte is None:
            # Sin proveedor no se gasta intento: no es un fallo de entrega sino
            # una configuracion que falta. Se anota para no volver a tomarlo en
            # esta corrida — si no, `tomar_uno` devuelve el mismo para siempre y
            # la corrida se consume sin atender a nadie.
            #
            # **No se hace `rollback` para soltar el candado.** Seria lo obvio y
            # esta mal: deshace tambien lo que el llamador tuviera pendiente en
            # esta sesion. No hace falta — no se escribio nada, y el candado se
            # suelta en el proximo commit o al cerrar la sesion.
            saltados.append(aviso.id)
            r.sin_proveedor += 1
            continue

        try:
            persona = validar_destinatario(db, aviso)
        except ErrorPermanente as exc:
            _rendirse(db, aviso, str(exc))
            r.fallidos += 1
            r.motivos.append(f"{aviso.id}: {exc}")
            continue

        _anotar_intento(db, aviso)

        if aviso.channel in SIN_TRANSPORTE:
            _entregado(db, aviso, None)
            r.entregados += 1
            continue

        try:
            id_proveedor = transporte.enviar(  # type: ignore[union-attr]
                destino=persona.email,
                asunto=aviso.subject or "",
                cuerpo=aviso.body,
                contexto=aviso.context or {},
            )
        except ErrorPermanente as exc:
            _rendirse(db, aviso, str(exc))
            r.fallidos += 1
            r.motivos.append(f"{aviso.id}: {exc}")
        except Exception as exc:
            motivo = f"{type(exc).__name__}: {exc}"
            if aviso.attempts >= MAX_INTENTOS:
                _rendirse(db, aviso, motivo)
                r.rendidos += 1
                r.motivos.append(f"{aviso.id}: se rindio tras {aviso.attempts} — {motivo}")
            else:
                # Se queda en `queued` con el reintento ya corrido por
                # `_anotar_intento`. No hace falta escribir nada mas que el
                # motivo, que es lo que permite diagnosticar sin reproducir.
                aviso.last_error = motivo[:2000]
                db.flush()
                db.commit()
                r.reintentables += 1
        else:
            _entregado(db, aviso, id_proveedor)
            r.entregados += 1

    return r


def atrasados(db: Session, *, horas: int = 24) -> int:
    """Cuantos avisos llevan mas de `horas` sin salir.

    Existe para que el despachador pueda gritar. Una cola que se detiene no
    produce ningun error —simplemente deja de entregar— y este sistema no puede
    permitirse que eso pase en silencio: son avisos de plazos legales.
    """
    corte = _ahora() - timedelta(hours=horas)
    vencimiento = func.coalesce(Notification.next_attempt_at, Notification.scheduled_at)
    return (
        db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.status == "queued",
                Notification.deleted_at.is_(None),
                vencimiento <= corte,
            )
        ).scalar()
        or 0
    )
