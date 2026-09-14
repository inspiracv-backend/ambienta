"""La historia de un registro, reunida de sus distintas fuentes (RF-113, #75).

## Que faltaba, medido el 7-sep-2026

**No el componente.** `HistorialTimeline` existe en el frontend y esta montado
en cinco pantallas de detalle. Lo que le falta es el dato:

| pieza | estado |
|---|---|
| `audit-log-store` del navegador | **nunca le pregunta a la API** — solo lo de esta sesion |
| `GET /system/audit-log` | existe, **cero llamadores** |
| filas en `audit_log` | **9.575**, invisibles |

El propio store lo dice en un comentario: *"Conectarlo es trabajo aparte: hay
que mapear la forma de la API a `AuditLogEntry`"*.

## El problema real: tres vocabularios para lo mismo

Es lo que haria que una union ingenua devolviera **cero eventos**:

| donde | como se llama una obligacion |
|---|---|
| `audit_log.entity_type` | `obligations` — el nombre de la **tabla** |
| `comments` / `entity_documents` | `obligation` — el nombre de **dominio** |
| `packages/shared` | `obligacion` — en **espanol** |

`audit_log` guarda el nombre de la tabla porque lo escribe el observador del
`flush`, que ve modelos y no conceptos de negocio. Cambiarlo seria reescribir
9.575 filas y romper el observador, asi que se traduce **al leer**.

**Y la traduccion no es una lista nueva**: sale de
`ANCLAJES[tipo].modelo.__tablename__`, o sea del mismo mapa que valida el
anclaje de RF-108 y resuelve el permiso de RF-111, preguntandole al modelo como
se llama su tabla. Una entidad nueva no necesita que nadie se acuerde de
agregarla en un cuarto lugar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.comentarios import Comment
from ..models.documents import Document, EntityDocument
from ..models.organization import User
from ..models.system import AuditLog
from .vinculos_de_documentos import ANCLAJES, comprobar_anclaje

#: Tope de eventos por respuesta. Un registro con mas historia la tiene, y la
#: respuesta lo dice con `hay_mas`: una lista cortada **en silencio** es la
#: misma trampa que las oportunidades del CRM filtradas en el navegador.
TOPE = 200

#: Las fuentes que hoy alimentan la historia.
FUENTES = ("actividad", "comentario", "adjunto")

#: **Las que RF-113 nombra y todavia no existen.**
#:
#: La captura de correos es RF-107 (#72) y no esta construida. Mostrar tres
#: fuentes y callarse la cuarta dejaria una linea de tiempo que **se ve
#: completa**, y alguien concluiria que sobre ese registro no hubo correos
#: cuando lo que pasa es que el sistema todavia no los mira. En un modulo cuya
#: razon de ser es "la informacion se maneja por correo y se pierde", esa
#: omision seria exactamente el error que viene a arreglar.
#:
#: Mismo criterio que la `periodicidad` vacia de `retc_systems` y que el
#: repositorio de plantillas Excel: lo que no se sabe, se dice.
FUENTES_PENDIENTES = ("correo",)


@dataclass
class Evento:
    """Un hecho de la historia, ya normalizado."""

    tipo: Literal["actividad", "comentario", "adjunto"]
    ocurrido_el: datetime
    #: `None` cuando el hecho no tiene autor identificable — por ejemplo lo que
    #: escribe una tarea de cron. Se deja en `None` en vez de poner "Sistema":
    #: inventarle un nombre a quien no lo tiene es lo mismo que atribuirle un
    #: comentario al primer administrador.
    actor_id: UUID | None = None
    actor: str | None = None
    resumen: str = ""
    detalle: dict[str, Any] = field(default_factory=dict)


@dataclass
class Historia:
    eventos: list[Evento]
    fuentes: tuple[str, ...] = FUENTES
    fuentes_pendientes: tuple[str, ...] = FUENTES_PENDIENTES
    #: `True` si se alcanzo el tope y hay historia anterior sin devolver.
    hay_mas: bool = False


def tabla_de(entity_type: str) -> str:
    """Como llama `audit_log` a esta entidad.

    Derivado del modelo, no de una lista. Ver el modulo.
    """
    return ANCLAJES[entity_type].modelo.__tablename__


#: Los verbos del observador del `flush`, en algo que se pueda leer.
#:
#: Lo que no reconoce **se muestra crudo**, igual que `lib/iso-vocabulario.ts`:
#: un verbo feo se arregla, uno escondido tras un guion no se entera nadie.
ACCIONES = {
    "create": "Creado",
    "update": "Modificado",
    "delete": "Eliminado",
    "login": "Ingreso",
}


def _nombres(db: Session, ids: set[UUID]) -> dict[UUID, str]:
    """Los nombres de los actores, en una consulta y no en N."""
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {
        u.id: u.full_name
        for u in db.scalars(select(User).where(User.id.in_(ids))).all()
    }


def construir(db: Session, entity_type: str, entity_id: UUID) -> Historia:
    """La historia de un registro: actividad, conversacion y adjuntos.

    Se une **en el servidor** y no en el navegador: el orden cronologico entre
    fuentes distintas se decide una vez, y dos clientes que lo entrelacen por su
    cuenta mostrarian dos historias distintas del mismo registro.

    Del mas reciente al mas antiguo, igual que el componente que ya existe: en
    una fiscalizacion la primera pregunta es *que paso al final*.
    """
    comprobar_anclaje(db, entity_type, entity_id)
    tabla = tabla_de(entity_type)
    eventos: list[Evento] = []

    # ── El registro de actividades (RNF-08, RNF-25) ──────────────────────
    #
    # La linea de tiempo lo **muestra**, no lo reemplaza: la epica #31 lo dice
    # explicito. Se pide `TOPE + 1` para saber si hay mas sin traerlo todo.
    actividad = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == tabla, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.occurred_at.desc())
        .limit(TOPE + 1)
    ).all()
    for a in actividad:
        eventos.append(
            Evento(
                tipo="actividad",
                ocurrido_el=a.occurred_at,
                actor_id=a.actor_user_id,
                resumen=ACCIONES.get(a.action, a.action),
                detalle={
                    "accion": a.action,
                    # Que campos cambiaron, no sus valores: los valores pueden
                    # traer datos que esta pantalla no deberia mostrar, y para
                    # leer la historia alcanza con saber que se toco.
                    "campos": sorted((a.after_data or {}).keys()),
                    "motivo": a.reason,
                },
            )
        )

    # ── La conversacion (RF-111) ─────────────────────────────────────────
    comentarios = db.scalars(
        select(Comment)
        .where(
            Comment.entity_type == entity_type,
            Comment.entity_id == entity_id,
            Comment.deleted_at.is_(None),
        )
        .order_by(Comment.created_at.desc())
        .limit(TOPE + 1)
    ).all()
    for c in comentarios:
        eventos.append(
            Evento(
                tipo="comentario",
                ocurrido_el=c.created_at,
                actor_id=c.author_user_id,
                resumen="Comento" if c.parent_id is None else "Respondio",
                detalle={
                    "comment_id": str(c.id),
                    "cuerpo": c.body,
                    "es_respuesta": c.parent_id is not None,
                    "editado": c.edited_at is not None,
                },
            )
        )

    # ── Los adjuntos (RF-108) ────────────────────────────────────────────
    vinculos = db.scalars(
        select(EntityDocument)
        .where(
            EntityDocument.entity_type == entity_type,
            EntityDocument.entity_id == entity_id,
            EntityDocument.deleted_at.is_(None),
        )
        .order_by(EntityDocument.created_at.desc())
        .limit(TOPE + 1)
    ).all()
    documentos = {
        d.id: d
        for d in (
            db.scalars(
                select(Document).where(Document.id.in_([v.document_id for v in vinculos]))
            ).all()
            if vinculos
            else []
        )
    }
    for v in vinculos:
        doc = documentos.get(v.document_id)
        eventos.append(
            Evento(
                tipo="adjunto",
                ocurrido_el=v.created_at,
                actor_id=v.created_by,
                resumen="Adjunto un documento",
                detalle={
                    "document_id": str(v.document_id),
                    # Si RLS no deja ver el documento, se dice — no se esconde
                    # el evento. Que exista un respaldo que esta sesion no puede
                    # abrir es informacion, no ruido.
                    "codigo": doc.code if doc else None,
                    "titulo": doc.title if doc else None,
                    "proposito": v.purpose,
                },
            )
        )

    eventos.sort(key=lambda e: e.ocurrido_el, reverse=True)
    hay_mas = len(eventos) > TOPE
    eventos = eventos[:TOPE]

    # Una consulta para todos los actores, no una por evento.
    nombres = _nombres(db, {e.actor_id for e in eventos if e.actor_id})
    for e in eventos:
        e.actor = nombres.get(e.actor_id) if e.actor_id else None

    return Historia(eventos=eventos, hay_mas=hay_mas)
