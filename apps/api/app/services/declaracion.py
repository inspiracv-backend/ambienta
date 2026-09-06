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

from sqlalchemy import func, select

from ..models.obligations import DeclarationSubmission, Obligation

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


#: El estado de una presentacion mientras espera respuesta del portal.
PRESENTADA = "submitted"


def presentacion_vigente(
    db: Session, obligacion: Obligation
) -> DeclarationSubmission | None:
    """La ultima presentacion de esta obligacion, si hay alguna.

    "Ultima" por `version_no` y no por fecha: dos presentaciones del mismo dia
    tienen la misma fecha y distinto numero, y el numero es el que ordena.
    """
    return db.scalars(
        select(DeclarationSubmission)
        .where(
            DeclarationSubmission.obligation_id == obligacion.id,
            DeclarationSubmission.deleted_at.is_(None),
        )
        .order_by(DeclarationSubmission.version_no.desc())
    ).first()


def _periodo(obligacion: Obligation) -> str | None:
    """El periodo declarado, en texto. `None` si la obligacion no lo tiene.

    `Obligation` guarda `period_start` y `period_end`, no una etiqueta. La
    primera version de esto escribia `obligacion.period_label` con un `hasattr`
    delante, o sea que **habria guardado `None` siempre y en silencio** — el
    mismo defecto de campo descartado que este repositorio ya sufrio dos veces
    con `planned_start_date` y con `process_id`.
    """
    if obligacion.period_start is None and obligacion.period_end is None:
        return None
    desde = obligacion.period_start.isoformat() if obligacion.period_start else "?"
    hasta = obligacion.period_end.isoformat() if obligacion.period_end else "?"
    return f"{desde} a {hasta}"


def _abrir_presentacion(
    db: Session, obligacion: Obligation, user_id: UUID | None
) -> DeclarationSubmission:
    """Anota **un intento mas** de presentar esta declaracion.

    ## Por que la obligacion no alcanza

    `obligations.external_receipt` guarda **un solo folio**. Una declaracion que
    se rechaza y se vuelve a presentar produce dos, y con una sola columna el
    primero se pierde al escribir el segundo — sin ningun error, y sin que nada
    diga que existio.

    Eso importa porque el folio **es el comprobante**: lo unico que la empresa
    puede mostrarle a un fiscalizador para sostener que declaro. Perder el de un
    intento rechazado borra la prueba de que ese intento ocurrio, y con ella la
    fecha en que se presento por primera vez — que es exactamente lo que se
    discute cuando hay un plazo de por medio.

    El numero de version es `max + 1` **por obligacion**, asi que el historial
    se lee como lo que es: v1 rechazada, v2 aceptada.
    """
    ultimo = db.scalar(
        select(func.max(DeclarationSubmission.version_no)).where(
            DeclarationSubmission.obligation_id == obligacion.id
        )
    )
    presentacion = DeclarationSubmission(
        tenant_id=obligacion.tenant_id,
        obligation_id=obligacion.id,
        # Se copian de la obligacion en vez de dejarlos vacios: la planta y el
        # periodo de una declaracion pueden cambiar despues, y el historial
        # tiene que decir contra que se presento **entonces**.
        facility_id=obligacion.facility_id,
        period_label=_periodo(obligacion),
        version_no=(ultimo or 0) + 1,
        status=PRESENTADA,
        prepared_by=user_id,
        submitted_by=user_id,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(presentacion)
    db.flush()
    return presentacion


def _cerrar_presentacion(
    db: Session,
    obligacion: Obligation,
    *,
    estado: str,
    user_id: UUID | None,
    folio: str | None = None,
    motivo: str | None = None,
) -> DeclarationSubmission | None:
    """Marca como resuelto el ultimo intento. `None` si no habia ninguno.

    **Devuelve `None` en vez de crear uno**, y eso es deliberado. Las
    obligaciones que ya estaban en `submitted` antes de que este historial
    existiera no tienen fila, y fabricarles una seria inventar una presentacion
    que nadie registro — con su fecha, su version y su autor, los tres falsos.
    El historial empieza vacio para ellas y dice la verdad.
    """
    presentacion = presentacion_vigente(db, obligacion)
    if presentacion is None:
        return None

    presentacion.status = estado
    presentacion.reviewed_by = user_id
    if folio:
        presentacion.external_folio = folio
    if motivo:
        # `submission_data` es jsonb: se reemplaza el diccionario entero, o
        # SQLAlchemy no detecta el cambio y el `UPDATE` sale sin esta clave.
        presentacion.submission_data = {
            **(presentacion.submission_data or {}),
            "motivo_rechazo": motivo,
        }
    db.flush()
    return presentacion


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
    # **El historial lo escribe el servicio, no el router.** Hay cuatro caminos
    # que mueven una declaracion y cada uno esta en un endpoint distinto; si el
    # rastro se dejara arriba, un endpoint nuevo se olvidaria y **no fallaria
    # nada** — simplemente esa presentacion no existiria. Es la misma razon por
    # la que el registro de actividades se engancha al `flush` de la sesion.
    _abrir_presentacion(db, obligacion, user_id)
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
    # La obligacion conserva el **ultimo** folio —es lo que lee la pantalla— y
    # el historial se queda con el de cada intento. Los dos, no uno: quitar la
    # columna rompe el frontend, y dejar solo la columna es el problema que este
    # historial existe para resolver.
    _cerrar_presentacion(
        db, obligacion, estado="accepted", user_id=user_id, folio=folio_final
    )
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
    # El motivo queda tambien en la presentacion rechazada. En la obligacion se
    # sobrescribe con el del proximo rechazo; en el historial cada intento
    # conserva el suyo, que es lo que permite ver **por que** hicieron falta
    # tres vueltas.
    _cerrar_presentacion(
        db, obligacion, estado="rejected", user_id=user_id, motivo=motivo
    )
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
