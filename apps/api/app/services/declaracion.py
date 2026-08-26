"""El ciclo de vida de una declaracion y su urgencia (epica #21).

Reune tres cosas que estaban sueltas o rotas:

## 1. La maquina de estados (#115)

`obligations.status` admite ocho valores y **solo dos transiciones estaban
escritas**: `submit` y un `fulfill` que no funcionaba. Aprobar y rechazar, que
son la otra mitad del flujo de RF-31, no existian pese a que el CHECK de la
base ya contempla `accepted` y `rejected`.

Y `fulfill_obligation` escribia `status = "fulfilled"`, **un valor que la base
rechaza**: el endpoint respondia 422 en el 100 % de los casos. Medido con una
sonda antes de tocar nada. Es la misma clase de error que ya tuvo
`evaluate_article` con `'not_evaluated'` — una lista de estados escrita de
memoria en vez de leida del esquema.

Las transiciones se declaran en un solo lugar (`TRANSICIONES`) en vez de
repartirse en `if` por cada endpoint. Un flujo repartido en cuatro funciones
termina permitiendo, en alguna de ellas, un salto que las otras prohiben.

## 2. El folio, y por que no basta con guardarlo (#114)

Aprobar una declaracion **exige el folio**. El folio es el comprobante que
devuelve el portal del Estado: es la unica prueba de que la declaracion se
presento de verdad. Aceptar sin el deja a la empresa con un "listo" en pantalla
y nada que mostrarle a un fiscalizador — que es exactamente el error mas caro
posible en este dominio, porque nadie lo descubre hasta la fiscalizacion.

## 3. La urgencia (#113)

Estaba calculada **solo en el navegador**. Nada la exponia desde el servidor,
asi que el correo de recordatorio, un informe o una integracion no tenian forma
de saber que era urgente sin reimplementar el criterio — y dos criterios que se
escriben dos veces se separan, como ya paso con el porcentaje de cumplimiento.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.obligations import Obligation

#: Que estados se puede alcanzar desde cada uno. Lo que no esta, no se puede.
#:
#: `closed` no tiene salida a proposito: una declaracion cerrada que vuelve
#: atras deja el historial contando una cosa distinta de la que paso. Si hay que
#: rectificar, se abre una declaracion nueva — que es lo que hace el propio
#: RETC, y por eso `declaration_submissions.status` tiene `rectified`.
TRANSICIONES: dict[str, set[str]] = {
    "draft": {"open", "in_progress", "submitted", "closed"},
    "open": {"in_progress", "submitted", "overdue", "closed"},
    "in_progress": {"submitted", "overdue", "closed"},
    "submitted": {"accepted", "rejected"},
    "rejected": {"in_progress", "submitted", "closed"},
    "accepted": {"closed"},
    "overdue": {"in_progress", "submitted", "closed"},
    "closed": set(),
}

#: Cuando una declaracion ya no corre plazo.
RESUELTOS = frozenset({"accepted", "closed"})

#: Dias antes del vencimiento que separan cada nivel de urgencia.
#:
#: **No son las ventanas de aviso.** Esas son 15/7/3/1 y viven en el trabajo de
#: notificaciones (#120): dicen *cuando escribirle a alguien*. Estas dicen *de
#: que color se ve*, que es una pregunta distinta y con menos escalones —
#: un semaforo de seis colores no es un semaforo.
DIAS_CRITICO = 3
DIAS_PROXIMO = 15


class ErrorDeDeclaracion(Exception):
    """La operacion pedida no corresponde al estado actual."""


class TransicionInvalida(ErrorDeDeclaracion):
    """Ese salto de estado no existe."""


class FaltaElFolio(ErrorDeDeclaracion):
    """No se puede aceptar una declaracion sin el comprobante del portal."""


@dataclass(frozen=True)
class Urgencia:
    """Como se ve una declaracion segun lo que le queda de plazo."""

    nivel: str
    dias_restantes: int | None

    #: Los cinco niveles. `sin_plazo` no es un descuido: una obligacion sin
    #: `due_at` existe —una tarea permanente, un compromiso sin fecha— y
    #: pintarla de verde diria que va bien cuando en realidad no se sabe.
    NIVELES = ("resuelta", "vencida", "critica", "proxima", "vigente", "sin_plazo")


def urgencia(obligacion: Obligation, ahora: datetime | None = None) -> Urgencia:
    """El semaforo de una declaracion (#113).

    El orden de las preguntas importa y no es intercambiable:

    1. **Resuelta primero.** Una declaracion aceptada la semana pasada, con
       vencimiento ayer, no esta vencida: esta lista. Preguntar por la fecha
       antes que por el estado la pintaria de rojo para siempre.
    2. **Sin plazo despues.** Sin `due_at` no hay resta que hacer, y suponer
       una fecha seria inventarla.
    3. Recien entonces, los dias.

    `ahora` se inyecta para poder probarlo sin esperar tres dias.
    """
    ahora = ahora or datetime.now(timezone.utc)

    if obligacion.status in RESUELTOS:
        return Urgencia("resuelta", None)
    if obligacion.due_at is None:
        return Urgencia("sin_plazo", None)

    vence = obligacion.due_at
    if vence.tzinfo is None:  # pragma: no cover - depende del driver
        vence = vence.replace(tzinfo=timezone.utc)

    # Se cuentan dias completos hacia arriba: a las 23:00 del dia anterior al
    # vencimiento queda 1 dia, no 0. Truncar hacia abajo diria "vence hoy" toda
    # la vispera, y quien lo lee cree que ya no alcanza.
    segundos = (vence - ahora).total_seconds()
    dias = -((-segundos) // 86400)
    dias = int(dias)

    if segundos < 0:
        return Urgencia("vencida", dias)
    if dias <= DIAS_CRITICO:
        return Urgencia("critica", dias)
    if dias <= DIAS_PROXIMO:
        return Urgencia("proxima", dias)
    return Urgencia("vigente", dias)


def _mover(db: Session, obligacion: Obligation, destino: str) -> Obligation:
    permitidos = TRANSICIONES.get(obligacion.status, set())
    if destino not in permitidos:
        raise TransicionInvalida(
            f"Una declaracion en '{obligacion.status}' no puede pasar a '{destino}'. "
            f"Desde aca solo se puede: {', '.join(sorted(permitidos)) or 'nada'}."
        )
    obligacion.status = destino
    db.flush()
    db.refresh(obligacion)
    return obligacion


def enviar(db: Session, *, obligacion: Obligation, user_id: UUID | None = None) -> Obligation:
    """La declaracion se presento y queda esperando revision (RF-31)."""
    obligacion.submitted_at = datetime.now(timezone.utc)
    if user_id is not None:
        obligacion.updated_by = user_id
    return _mover(db, obligacion, "submitted")


def aprobar(
    db: Session,
    *,
    obligacion: Obligation,
    folio: str | None = None,
    user_id: UUID | None = None,
) -> Obligation:
    """Acepta la declaracion. **Exige el folio del portal** (#114).

    El folio puede venir de esta llamada o estar ya registrado. Lo que no se
    admite es aceptar sin ninguno: sin comprobante, "declarado" es una
    afirmacion que la empresa no puede sostener frente a un fiscalizador.
    """
    folio_final = (folio or obligacion.external_receipt or "").strip()
    if not folio_final:
        raise FaltaElFolio(
            "Para aceptar la declaracion hace falta el folio que devolvio el "
            "sistema oficial. Es el unico comprobante de que se presento."
        )

    obligacion.external_receipt = folio_final
    if user_id is not None:
        obligacion.updated_by = user_id
    return _mover(db, obligacion, "accepted")


def rechazar(
    db: Session, *, obligacion: Obligation, motivo: str, user_id: UUID | None = None
) -> Obligation:
    """Devuelve la declaracion a quien la preparo, **con el motivo**.

    El motivo es obligatorio. Un rechazo sin explicacion obliga a adivinar que
    corregir, y mientras se adivina el plazo sigue corriendo.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErrorDeDeclaracion(
            "Un rechazo sin motivo obliga a adivinar que corregir. Indica el motivo."
        )

    # `data` es jsonb: se reemplaza el diccionario entero en vez de mutarlo, o
    # SQLAlchemy no detecta el cambio y el `UPDATE` sale sin esta clave.
    obligacion.data = {**(obligacion.data or {}), "motivo_rechazo": motivo}
    if user_id is not None:
        obligacion.updated_by = user_id
    return _mover(db, obligacion, "rejected")


def registrar_folio(db: Session, *, obligacion: Obligation, folio: str) -> Obligation:
    """Anota el comprobante sin cambiar el estado.

    Existe aparte de `aprobar` porque son dos momentos distintos: quien declara
    en el portal copia el folio apenas lo recibe, y quien aprueba puede ser otra
    persona y otro dia.
    """
    folio = (folio or "").strip()
    if not folio:
        raise ErrorDeDeclaracion("El folio no puede ir vacio.")
    obligacion.external_receipt = folio
    db.flush()
    db.refresh(obligacion)
    return obligacion
