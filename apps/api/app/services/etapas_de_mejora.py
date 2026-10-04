"""El ciclo de tratamiento de un registro de mejora (RF-97, RF-98, #38, #43).

## Que hace este modulo y que no

Decide **cuando una etapa se puede dar por completada** y **cuando el registro
se puede cerrar**. No decide el orden: eso es configuracion por empresa, y el
diseno lo deja explicito —el sistema del cliente pone el analisis de causa antes
de la correccion, y los dos ordenes son defendibles—.

## La regla que justifica el modulo entero

**El cierre exige `eficaz is True`, no un valor truthy.** Es RF-98, y es la
diferencia entre un sistema de gestion y un registro de tareas: una accion
correctiva que no se verifico no esta cerrada, y una que se verifico y no
funciono vuelve a tratamiento.

Los cinco campos del seguimiento son `Seleccione… / SI / NO` en el sistema del
cliente. Como booleano, "todavia no lo verifique" se vuelve "No" — que en tres
de las cuatro preguntas es la respuesta **favorable**. O sea que el defecto
silencioso cerraria la verificacion a favor, justo donde la norma pide rigor.

## El plazo se calcula, y por eso el catalogo no es decorativo

`improvement_severities.days_to_close` existe desde `db/25` y **nadie lo
usaba**: `due_date` se pedia a mano. Aca se calcula — cuando la empresa declara
el plazo de su escala. Mientras siga en NULL —hoy lo esta, a proposito, porque
sembrar 60/30/15 seria inventarle el compromiso a la empresa— se sigue pidiendo
a mano y esta funcion devuelve `None`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.audit import (
    ImprovementCommitment,
    ImprovementSeverity,
    ImprovementStageEntry,
    Nonconformity,
)
from ..schemas.audit import COMPROMISO_POR_CAMPO
from .husos import hoy_de

#: El orden por defecto, alineado a ISO 9001 §10.2.1: primero reaccionar,
#: despues analizar. **Es el defecto, no una constante del sistema** — la
#: empresa puede permutarlo, con el registro siempre primero y el seguimiento
#: siempre ultimo.
ORDEN_POR_DEFECTO = (
    "registro",
    "correccion",
    "analisis_causa",
    "accion_correctiva",
    "seguimiento",
)

#: Los tipos que **no** recorren las cinco.
#:
#: No hay "correccion inmediata" de una oportunidad, ni causa raiz que analizar.
#: Hacerlos pasar por las cinco con los campos vacios seria peor dato que
#: saltarlas: un registro que dice "corregido: (nada)" es una afirmacion falsa.
ETAPAS_REDUCIDAS = ("riesgo", "oportunidad")
ORDEN_REDUCIDO = ("registro", "accion_correctiva", "seguimiento")


class ErrorDeEtapa(Exception):
    """Algo del ciclo que el llamador puede corregir."""


def orden_de(registro: Nonconformity) -> tuple[str, ...]:
    """Que etapas recorre este registro, en orden."""
    if registro.record_type in ETAPAS_REDUCIDAS:
        return ORDEN_REDUCIDO
    return ORDEN_POR_DEFECTO


def plazo_de(db: Session, tenant_id: UUID, severidad: str) -> int | None:
    """Cuantos dias da la empresa para cerrar esa severidad, o `None`.

    **`None` no es cero.** Significa que la empresa todavia no declaro su
    compromiso, y en ese caso la fecha limite se sigue pidiendo a mano. Inventar
    un plazo produce una fecha que nadie acordo — la empresa cree que va a
    tiempo, que en cumplimiento es el peor error posible. Mismo criterio que la
    `periodicidad` vacia de `retc_systems`.
    """
    fila = db.scalars(
        select(ImprovementSeverity).where(
            ImprovementSeverity.tenant_id == tenant_id,
            ImprovementSeverity.code == severidad,
            ImprovementSeverity.active.is_(True),
            ImprovementSeverity.deleted_at.is_(None),
        )
    ).first()
    return fila.days_to_close if fila is not None else None


def calcular_due_date(
    db: Session, registro: Nonconformity, *, desde: date | None = None
) -> date | None:
    """La fecha limite de una etapa, derivada del catalogo de la empresa.

    Se cuenta **desde la deteccion** y no desde hoy: el plazo de una no
    conformidad corre desde que se detecto, no desde que alguien abrio la
    pantalla.

    ## Y el respaldo usa `hoy_de`, no `date.today()`

    Lo marco el detector de "fechas de calendario medidas en horas" veinte
    minutos despues de escribir esta funcion, y tenia razon: **`date.today()` no
    es "hoy", es "hoy donde corre este proceso"**. La base va en UTC y el host
    en hora de Chile, asi que pasadas las 20:00 estan en dias distintos — y
    `countries` tiene cinco husos, o sea que no es una constante disfrazada.

    Sumar dias a un `date` si es aritmetica de calendario y esta bien: el
    problema era de donde salia el punto de partida.
    """
    dias = plazo_de(db, registro.tenant_id, registro.severity)
    if dias is None:
        return None
    base = desde or (
        registro.detected_at.date()
        if registro.detected_at
        else hoy_de(db, registro.tenant_id)
    )
    return base + timedelta(days=dias)


def etapas_de(db: Session, nonconformity_id: UUID) -> list[ImprovementStageEntry]:
    """Las etapas de un registro, en el orden del ciclo y no por fecha.

    Ordenar por `created_at` mostraria el ciclo en el orden en que alguien
    completo los formularios, que no es el orden del proceso.
    """
    filas = list(
        db.scalars(
            select(ImprovementStageEntry).where(
                ImprovementStageEntry.nonconformity_id == nonconformity_id,
                ImprovementStageEntry.deleted_at.is_(None),
            )
        ).all()
    )
    posicion = {k: i for i, k in enumerate(ORDEN_POR_DEFECTO)}
    return sorted(filas, key=lambda e: posicion.get(e.kind, 99))


def puede_cerrarse(db: Session, registro: Nonconformity) -> tuple[bool, str | None]:
    """Si el registro cumple RF-98, y si no, por que.

    Devuelve el motivo en vez de un booleano pelado porque **"no se puede
    cerrar" sin decir por que manda a adivinar**, y las tres causas tienen
    arreglos distintos: falta ejecutar una etapa, falta verificar, o se verifico
    y no fue eficaz.
    """
    etapas = {e.kind: e for e in etapas_de(db, registro.id)}

    # **Un registro SIN ninguna etapa no queda bloqueado**, y es deliberado.
    #
    # El ciclo tipado existe desde el 12-sep. Los registros anteriores no tienen
    # etapas, y exigirselas dejaria sin poder cerrarse a todo lo que ya estaba
    # en tratamiento — con el mensaje "faltan etapas" y sin forma de entender
    # por que, porque nunca las tuvieron. Esos siguen con la regla anterior: al
    # menos un plan de accion verificado (`services/audits.py`).
    #
    # Todo registro nuevo nace con su ciclo sembrado, asi que la excepcion se
    # agota sola. Y **no es una puerta trasera**: no hay forma de quitarle las
    # etapas a un registro que las tiene — no existe el borrado de una etapa,
    # justamente por esto.
    if not etapas:
        return True, None

    faltan = [k for k in orden_de(registro) if k not in etapas]
    if faltan:
        return False, (
            "Faltan etapas del ciclo: " + ", ".join(faltan) + "."
        )

    sin_completar = [
        k for k, e in etapas.items() if e.completada_en is None
    ]
    if sin_completar:
        return False, (
            "Hay etapas sin completar: " + ", ".join(sorted(sin_completar)) + "."
        )

    seguimiento = etapas.get("seguimiento")
    if seguimiento is None or seguimiento.eficaz is None:
        # **`is None` y no falsy.** Sin verificar no es "no fue eficaz", y el
        # mensaje tiene que distinguirlos: uno se arregla verificando y el otro
        # volviendo a tratamiento.
        return False, (
            "El seguimiento todavia no dice si la accion fue eficaz. Sin "
            "verificar no es lo mismo que no haber funcionado."
        )
    if seguimiento.eficaz is not True:
        return False, (
            "El seguimiento dice que la accion NO fue eficaz: el registro "
            "vuelve a tratamiento en vez de cerrarse."
        )

    # **Las salidas comprometidas no bloquean el cierre, pero sin responsable ni
    # fecha no se le avisan a nadie** — que es el defecto que esto vino a
    # arreglar, con otro nombre. El registro se cierra; la salida sigue viva.
    sin_dueno = [
        c.kind
        for c in compromisos_pendientes(db, registro.id)
        if c.responsable_user_id is None or c.due_date is None
    ]
    if sin_dueno:
        return False, (
            "Hay salidas comprometidas sin responsable o sin fecha: "
            + ", ".join(sorted(sin_dueno))
            + ". El registro se puede cerrar, pero la salida tiene que quedar a cargo de alguien."
        )
    return True, None


#: Los campos del seguimiento que describen **una** verificacion. Al volver a
#: la accion correctiva se guardan y se vacian: la siguiente es otra.
_DE_LA_VERIFICACION = (
    "fecha_ejecucion",
    "eficaz",
    "causa_se_repitio",
    "cumplio_proposito",
    "requiere_actualizar_riesgos",
    "requiere_cambios_sgc",
    "observaciones",
)


def comprometer_salidas(db: Session, registro: Nonconformity, seguimiento: ImprovementStageEntry) -> int:
    """Crea los compromisos de las salidas que la verificacion dejo abiertas.

    ISO 9001 10.2.1 e y f. Las dos preguntas del seguimiento eran casillas sin
    consecuencia hasta el 4-oct: se marcaba "Si", se cerraba el registro, y el
    sistema no volvia a mencionarlo. Ahora cada "Si" deja un compromiso
    **pendiente**, que sobrevive al cierre del registro y se ve en la lista de
    salidas pendientes.

    Responsable y fecha nacen vacios —al marcar la casilla todavia no se saben,
    e inventarlos es lo que este repositorio evita con los plazos—, pero el
    cierre del registro los exige: ver `puede_cerrarse`.

    Un "No" o un "sin responder" **no retira** un compromiso que ya existe: lo
    prometido se cumple o se descarta con justificacion, no se borra cambiando
    una casilla. Idempotente: una fila por salida y por registro.
    """
    nuevos = 0
    for campo, kind in COMPROMISO_POR_CAMPO.items():
        if getattr(seguimiento, campo) is not True:
            continue
        ya_esta = db.scalar(
            select(ImprovementCommitment).where(
                ImprovementCommitment.nonconformity_id == registro.id,
                ImprovementCommitment.kind == kind,
                ImprovementCommitment.deleted_at.is_(None),
            )
        )
        if ya_esta is not None:
            continue
        db.add(
            ImprovementCommitment(
                tenant_id=registro.tenant_id,
                nonconformity_id=registro.id,
                stage_entry_id=seguimiento.id,
                kind=kind,
                status="pendiente",
            )
        )
        nuevos += 1
    if nuevos:
        db.flush()
    return nuevos


def compromisos_pendientes(db: Session, registro_id: UUID) -> list[ImprovementCommitment]:
    """Las salidas de este registro que todavia nadie ejecuto ni descarto."""
    return list(
        db.scalars(
            select(ImprovementCommitment).where(
                ImprovementCommitment.nonconformity_id == registro_id,
                ImprovementCommitment.status == "pendiente",
                ImprovementCommitment.deleted_at.is_(None),
            )
        ).all()
    )


def devolver_a_accion_correctiva(db: Session, registro: Nonconformity) -> bool:
    """Si el seguimiento concluyo que la accion **no** fue eficaz, el registro
    vuelve a la accion correctiva (ISO 9001 10.2, RF-98).

    Hasta el 4-oct "no eficaz" solo impedia cerrar: el registro quedaba con
    todas sus etapas completas y un seguimiento negativo, y nada decia que habia
    que volver a actuar. El spec pedia que volviera, y que se viera.

    - La **accion correctiva** queda por hacer otra vez (sin fecha ni marca).
    - El **seguimiento** queda sin verificar: la verificacion que fallo se
      guarda en `datos.verificaciones_no_eficaces` y sus campos se vacian,
      porque la proxima verificacion es sobre otra accion. Si quedaran, la
      pantalla —que reenvia el formulario entero— volveria a disparar esto en
      cada guardado.
    - El registro pasa a `action_plan`. Ese cambio de estado es lo que queda en
      **su** historia: el registro de actividades lo anota solo.

    Devuelve `False` si el registro no tiene etapa de accion correctiva.
    """
    etapas = {e.kind: e for e in etapas_de(db, registro.id)}
    accion = etapas.get("accion_correctiva")
    seguimiento = etapas.get("seguimiento")
    if accion is None:
        return False

    if seguimiento is not None:
        fallida = {
            campo: (
                getattr(seguimiento, campo).isoformat()
                if hasattr(getattr(seguimiento, campo), "isoformat")
                else getattr(seguimiento, campo)
            )
            for campo in _DE_LA_VERIFICACION
        }
        fallida["registrada_en"] = datetime.now(timezone.utc).isoformat()
        datos = dict(seguimiento.datos or {})
        datos["verificaciones_no_eficaces"] = [*datos.get("verificaciones_no_eficaces", []), fallida]
        seguimiento.datos = datos
        for campo in _DE_LA_VERIFICACION:
            setattr(seguimiento, campo, None)
        seguimiento.completada_en = None

    accion.fecha_ejecucion = None
    accion.completada_en = None
    registro.status = "action_plan"
    db.flush()
    return True


def exigir_cierre(db: Session, registro: Nonconformity) -> None:
    """Igual que `puede_cerrarse`, pero levanta 409 con el motivo.

    **409 y no 422**: el cuerpo esta bien y la peticion es legitima; lo que pasa
    es que el registro esta en un estado que no admite el cierre. Un 422 diria
    "corrige lo que mandaste", y no hay nada que corregir ahi.
    """
    ok, motivo = puede_cerrarse(db, registro)
    if not ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=motivo)


def sembrar_ciclo(
    db: Session, registro: Nonconformity, *, tenant_id: UUID
) -> list[ImprovementStageEntry]:
    """Crea las etapas que le tocan al registro, vacias y con su plazo.

    **Se crean todas al registrar y no una a una al avanzar.** Una etapa que no
    existe todavia no se puede asignar ni avisar, y el aviso por etapa (RF-99)
    es justamente lo que hace que el ciclo no se detenga: si la fila aparece
    recien cuando alguien llega a ella, el recordatorio llega tarde por
    definicion.

    Idempotente: no duplica lo que ya este creado.
    """
    ya = {e.kind for e in etapas_de(db, registro.id)}
    vencimiento = calcular_due_date(db, registro)
    creadas = []
    for kind in orden_de(registro):
        if kind in ya:
            continue
        fila = ImprovementStageEntry(
            tenant_id=tenant_id,
            nonconformity_id=registro.id,
            kind=kind,
            due_date=vencimiento,
        )
        if kind == "registro":
            # **La etapa de registro se cumple al registrar.** Hasta el 13-sep
            # nacia vacia, y ninguna pantalla la muestra ni la completa — asi
            # que `puede_cerrarse` respondia "hay etapas sin completar:
            # registro" para siempre y ningun registro nuevo se podia cerrar.
            # Su fecha es la de deteccion: es cuando el hallazgo quedo anotado.
            fila.fecha_ejecucion = (
                registro.detected_at.date()
                if registro.detected_at
                else hoy_de(db, tenant_id)
            )
            fila.completada_en = datetime.now(timezone.utc)
        db.add(fila)
        creadas.append(fila)
    if creadas:
        db.flush()
    return creadas
