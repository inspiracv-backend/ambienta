"""El informe de auditoria: matriz por proceso y tasa de cierre (#42, RF-101).

## Los conteos se derivan, no se guardan

Todo lo contable de este informe se calcula cada vez que se pide. Guardarlo
seria mas rapido de leer y **es la forma mas corta de que el informe y el
sistema digan cosas distintas** — y el que miente siempre es el guardado, porque
el otro se actualiza solo. Un hallazgo que se cierra despues de emitir el
informe tiene que cambiar el numero la proxima vez que alguien lo abra.

Lo unico persistido es lo que **escribe el auditor** y no se puede derivar de
ningun lado: la clasificacion de cada proceso, su conclusion y que evidencia
tuvo a la vista (`audit_process_results`).

## "Sin datos" no es cero, y en este archivo hay tres oportunidades de
## equivocarse

Es el error que este repositorio ya cometio cuatro veces —`normSemaforo(0)`, el
tablero pintando en rojo las plantas sin evaluar, la cobertura, los reportes— y
aca vuelve a estar servido:

| situacion | lo facil | lo correcto |
|---|---|---|
| Auditoria sin items | `0 %` de cobertura | `None`: no se midio nada |
| Proceso sin veredicto del auditor | "no conforme" | `no_auditado`, explicito |
| Ciclo anterior sin hallazgos | tasa de cierre `0 %` | `None`: no habia que cerrar nada |

El tercero es el peor de los tres. Una tasa de cierre en 0 % se lee como "no
cerraron nada de lo anterior", que es una acusacion; la realidad puede ser que
la auditoria anterior no encontro nada, o que no hay auditoria anterior. Los
tres estados se ven identicos si se devuelve un cero.

## La tasa de cierre conecta un ciclo con el siguiente

Sale del informe del cliente, que reporta cuantos hallazgos de la auditoria
anterior se cerraron (design.md §6). "La anterior" es la auditoria **cerrada mas
reciente de la misma planta y del mismo tipo** que empezo antes que esta: una
auditoria interna no se compara con una de un certificador externo, porque no
buscan lo mismo ni las cierra la misma gente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.audit import (
    Audit,
    AuditItem,
    AuditProcessResult,
    Nonconformity,
)
from ..models.organization import Process

#: Lo que cuenta como "cerrado" al medir el ciclo anterior.
#:
#: `rejected` **no entra**: un hallazgo rechazado es uno que se decidio que no
#: correspondia, no uno que se trato. Contarlo como cerrado inflaria la tasa
#: justo con los casos en que no se hizo nada.
ESTADO_CERRADO = "closed"

#: El veredicto de un proceso que la auditoria no alcanzo a mirar.
#:
#: Existe como valor y no como ausencia porque son cosas distintas: "no lo
#: auditamos" es informacion para el dueno del proceso, y una fila vacia se lee
#: como un descuido del informe.
SIN_AUDITAR = "no_auditado"


@dataclass
class FilaDeProceso:
    """Una fila de la matriz. Mezcla derivado y escrito, y lo dice."""

    proceso_id: str
    proceso_nombre: str
    #: Derivado: los articulos contra los que se pregunto.
    clausulas_auditadas: list[str] = field(default_factory=list)
    #: Derivado: cuantas preguntas y como salieron.
    items: int = 0
    items_conformes: int = 0
    items_no_conformes: int = 0
    #: Derivado: los registros de mejora que salieron de este proceso.
    hallazgos: list[str] = field(default_factory=list)
    #: Escrito por el auditor. `no_auditado` cuando no dejo veredicto.
    clasificacion: str = SIN_AUDITAR
    conclusion: str | None = None
    evidencia_revisada: str | None = None


@dataclass
class ResumenEjecutivo:
    procesos_auditados: int = 0
    #: Preguntas que no pertenecen a ningun proceso: requisitos generales del
    #: sistema de gestion. **Van aparte y no repartidos**, por lo mismo que
    #: `items_sin_articulo` en la cobertura.
    items_sin_proceso: int = 0
    no_conformidades: int = 0
    observaciones: int = 0
    oportunidades_de_mejora: int = 0
    #: `None` cuando la auditoria no tiene ni una pregunta: no es 0 %, es que no
    #: se midio nada.
    conformidad: float | None = None


@dataclass
class Informe:
    audit_id: str
    codigo: str
    titulo: str
    estado: str
    resumen: ResumenEjecutivo
    matriz: list[FilaDeProceso]
    #: `None` en tres casos que **no son cero**: no hay auditoria anterior, la
    #: anterior no encontro nada, o la anterior no esta cerrada.
    tasa_de_cierre_del_ciclo_anterior: float | None = None
    #: Por que la tasa vino vacia. Sin esto, `null` obliga a adivinar cual de
    #: los tres casos es, y son distintos para quien lee el informe.
    motivo_sin_tasa: str | None = None
    auditoria_anterior_id: str | None = None


def _auditoria_anterior(db: Session, auditoria: Audit) -> Audit | None:
    """La cerrada mas reciente de la misma planta y tipo, anterior a esta."""
    if auditoria.planned_start is None:
        return None
    return db.scalars(
        select(Audit)
        .where(
            Audit.tenant_id == auditoria.tenant_id,
            Audit.id != auditoria.id,
            Audit.facility_id == auditoria.facility_id,
            Audit.audit_type == auditoria.audit_type,
            Audit.status == "closed",
            Audit.planned_start < auditoria.planned_start,
            Audit.deleted_at.is_(None),
        )
        .order_by(Audit.planned_start.desc())
        .limit(1)
    ).first()


def _hallazgos_de(db: Session, auditoria_id: UUID) -> list[Nonconformity]:
    """Los registros de mejora que salieron de las preguntas de esa auditoria."""
    items = db.scalars(
        select(AuditItem.id).where(
            AuditItem.audit_id == auditoria_id, AuditItem.deleted_at.is_(None)
        )
    ).all()
    if not items:
        return []
    return list(
        db.scalars(
            select(Nonconformity).where(
                Nonconformity.audit_item_id.in_(items),
                Nonconformity.deleted_at.is_(None),
            )
        ).all()
    )


def tasa_de_cierre(
    db: Session, auditoria: Audit
) -> tuple[float | None, str | None, str | None]:
    """`(tasa, motivo_si_vacia, id_de_la_anterior)`.

    Devuelve `None` y **dice por que** en vez de un cero. Un 0 % se lee como
    "no cerraron nada de lo anterior", que es una acusacion; los otros dos casos
    —no hay ciclo anterior, o el anterior no encontro nada— no lo son, y con un
    cero los tres se ven iguales.
    """
    anterior = _auditoria_anterior(db, auditoria)
    if anterior is None:
        return None, "No hay una auditoria cerrada anterior de la misma planta y tipo.", None

    hallazgos = _hallazgos_de(db, anterior.id)
    if not hallazgos:
        return (
            None,
            "La auditoria anterior no dejo hallazgos, asi que no habia nada que cerrar.",
            str(anterior.id),
        )

    cerrados = sum(1 for h in hallazgos if h.status == ESTADO_CERRADO)
    return round(cerrados / len(hallazgos) * 100, 1), None, str(anterior.id)


def construir(db: Session, auditoria_id: UUID) -> Informe:
    """El informe completo. Todo lo contable sale de las filas, ahora."""
    auditoria = db.get(Audit, auditoria_id)
    if auditoria is None:
        raise ValueError("Audit not found")

    items = list(
        db.scalars(
            select(AuditItem).where(
                AuditItem.audit_id == auditoria_id, AuditItem.deleted_at.is_(None)
            )
        ).all()
    )
    hallazgos = _hallazgos_de(db, auditoria_id)
    hallazgos_por_item: dict[UUID, list[Nonconformity]] = {}
    for h in hallazgos:
        hallazgos_por_item.setdefault(h.audit_item_id, []).append(h)

    veredictos = {
        v.process_id: v
        for v in db.scalars(
            select(AuditProcessResult).where(
                AuditProcessResult.audit_id == auditoria_id,
                AuditProcessResult.deleted_at.is_(None),
            )
        ).all()
    }

    # Los procesos que aparecen: los que tienen preguntas y los que tienen
    # veredicto. La union y no la interseccion — un proceso que el auditor
    # marco `no_auditado` sin hacerle preguntas es una fila legitima, y decir
    # "no lo miramos" es informacion.
    ids_de_proceso = {i.process_id for i in items if i.process_id} | set(veredictos)
    nombres = {
        p.id: p.name
        for p in db.scalars(
            select(Process).where(Process.id.in_(ids_de_proceso))
        ).all()
    } if ids_de_proceso else {}

    matriz: list[FilaDeProceso] = []
    for pid in ids_de_proceso:
        suyos = [i for i in items if i.process_id == pid]
        veredicto = veredictos.get(pid)
        fila = FilaDeProceso(
            proceso_id=str(pid),
            proceso_nombre=nombres.get(pid, "(proceso retirado)"),
            items=len(suyos),
            items_conformes=sum(1 for i in suyos if i.result == "conform"),
            items_no_conformes=sum(1 for i in suyos if i.result == "nonconform"),
            clausulas_auditadas=sorted(
                {str(i.article_compliance_id) for i in suyos if i.article_compliance_id}
            ),
            hallazgos=sorted(
                str(h.id) for i in suyos for h in hallazgos_por_item.get(i.id, [])
            ),
            clasificacion=veredicto.classification if veredicto else SIN_AUDITAR,
            conclusion=veredicto.conclusion if veredicto else None,
            evidencia_revisada=veredicto.evidence_reviewed if veredicto else None,
        )
        matriz.append(fila)
    matriz.sort(key=lambda f: f.proceso_nombre)

    evaluados = [i for i in items if i.result in ("conform", "nonconform")]
    resumen = ResumenEjecutivo(
        procesos_auditados=len(ids_de_proceso),
        items_sin_proceso=sum(1 for i in items if i.process_id is None),
        no_conformidades=sum(
            1 for h in hallazgos if h.record_type in (None, "no_conformidad")
        ),
        observaciones=sum(1 for i in items if i.result == "observation"),
        oportunidades_de_mejora=sum(
            1 for h in hallazgos if h.record_type == "oportunidad"
        ),
        # `None` y no 0 %: una auditoria sin nada evaluado no tiene 0 % de
        # conformidad, no tiene conformidad medida. Es el mismo criterio que
        # `CoberturaDeAuditoria.porcentaje`.
        conformidad=(
            round(
                sum(1 for i in evaluados if i.result == "conform") / len(evaluados) * 100,
                1,
            )
            if evaluados
            else None
        ),
    )

    tasa, motivo, anterior_id = tasa_de_cierre(db, auditoria)

    return Informe(
        audit_id=str(auditoria.id),
        codigo=auditoria.code,
        titulo=auditoria.title,
        estado=auditoria.status,
        resumen=resumen,
        matriz=matriz,
        tasa_de_cierre_del_ciclo_anterior=tasa,
        motivo_sin_tasa=motivo,
        auditoria_anterior_id=anterior_id,
    )
