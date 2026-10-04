"""La conversacion sobre un registro: hilos y menciones (RF-111, RF-112, #74).

## Que problema resuelve

La epica #31 lo dice con las palabras del cliente: *"la informacion se maneja
por correo y se pierde, sobre todo la de normativas, RCAs e ISO"*. Lo que se
pierde no es el dato —ese esta en la base— sino **la conversacion sobre el
dato**: por que se evaluo asi un articulo, quien dijo que la evidencia servia,
que se acordo cuando el plazo se corrio.

## Lo que este modulo decide, y por que

Tres reglas que no son de estilo:

1. **El anclaje se comprueba con el mapa de RF-108**, no con uno propio. Con
   dos listas, una entidad comentable y no vinculable —o al reves— seria un
   estado que nadie eligio y que solo se descubre usando el sistema.
2. **Una respuesta a una respuesta se rechaza**, no se reacomoda contra la
   raiz. Aplanarla es lo que hace un chat y aca cambia el registro: en una
   discusion sobre si una evidencia sirve, colgar la respuesta del comentario
   equivocado le atribuye al autor que le estaba contestando a otra persona.
3. **Mencionar a alguien de otra empresa falla igual que mencionar a alguien
   que no existe.** Mismo codigo y mismo mensaje: distinguirlos convierte el
   campo en un oraculo para enumerar usuarios ajenos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.comentarios import Comment, CommentMention
from ..models.notifications import Notification
from ..models.organization import User
from .vinculos_de_documentos import comprobar_anclaje

#: El mismo texto para las dos negativas de una mencion. Ver `_comprobar_menciones`.
MENCION_NO_VISIBLE = "Alguno de los usuarios mencionados no es de esta empresa."


def _comprobar_padre(db: Session, comentario_padre_id: UUID, entity_id: UUID) -> Comment:
    """El hilo es de un solo nivel, y el padre es de la misma entidad.

    Devuelve el padre. Levanta 422 en los dos casos malos, y el del segundo
    nivel **dice cual es la raiz**: el cliente sabe que hacer con eso, no sabe
    que su respuesta se movio sola.
    """
    padre = db.scalars(
        select(Comment).where(
            Comment.id == comentario_padre_id, Comment.deleted_at.is_(None)
        )
    ).first()
    if padre is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="parent_id no corresponde a un comentario de esta empresa.",
        )
    if padre.entity_id != entity_id:
        # Un hilo pertenece a un registro. Dejar que una respuesta apunte a un
        # comentario de otro registro produciria un hilo partido en dos fichas.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El comentario al que se responde es de otro registro.",
        )
    if padre.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Los hilos son de un solo nivel: hay que responder al "
                f"comentario raiz ({padre.parent_id})."
            ),
        )
    return padre


def _comprobar_menciones(db: Session, usuarios: list[UUID]) -> list[UUID]:
    """Cada mencionado tiene que ser visible para esta empresa.

    La visibilidad la decide **Postgres**: se lee con la sesion que ya tiene el
    tenant declarado, asi que un usuario de otra empresa devuelve cero por RLS.
    Es el unico filtro por empresa que existe en el sistema (CLAUDE.md §4).

    Se devuelven deduplicados conservando el orden: mencionar dos veces a la
    misma persona en un comentario es una sola mencion, y el indice unico de la
    base lo exige igual — sin esto el `INSERT` reventaria con un 500 en vez de
    hacer lo obvio.
    """
    unicos: list[UUID] = []
    for uid in usuarios:
        if uid not in unicos:
            unicos.append(uid)
    if not unicos:
        return []

    visibles = set(
        db.scalars(
            select(User.id).where(User.id.in_(unicos), User.deleted_at.is_(None))
        ).all()
    )
    if len(visibles) != len(unicos):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=MENCION_NO_VISIBLE,
        )
    return unicos


def _encolar_avisos(
    db: Session, comentario: Comment, mencionados: list[UUID], autor: User | None
) -> int:
    """Un aviso in-app por mencionado. Devuelve cuantos se encolaron.

    Va por `notifications` —la cola que ya existe, con su deduplicacion, sus
    reintentos y su despachador— y no por un canal propio. Ademas de no
    reescribir lo hecho, hay una razon de correccion: **la fila del aviso y el
    comentario que lo causa se escriben en la misma transaccion**, asi que no
    pueden discrepar.

    **Solo `in_app`.** El correo usa la misma cola y seria una linea mas, pero
    mandar un correo por cada mencion es una decision de producto —volumen,
    ruido, gente que deja de leerlos— y nadie la tomo. Encolar los dos "por si
    acaso" es como se llega a que el cliente pida apagar la funcionalidad.

    **Nadie se notifica a si mismo.** Mencionarse al escribir es frecuente
    ("me lo llevo yo") y un aviso por eso entrena a ignorarlos.
    """
    quien = autor.full_name if autor is not None and autor.full_name else "Alguien"
    encolados = 0
    for uid in mencionados:
        if uid == comentario.author_user_id:
            continue
        db.add(
            Notification(
                tenant_id=comentario.tenant_id,
                recipient_user_id=uid,
                channel="in_app",
                subject=f"{quien} te menciono en un comentario",
                body=comentario.body[:500],
                status="queued",
                # Una mencion, un aviso. El indice unico es
                # `(tenant, clave, destinatario)`.
                dedupe_key=f"mencion:{comentario.id}",
                context={
                    "comment_id": str(comentario.id),
                    "entity_type": comentario.entity_type,
                    "entity_id": str(comentario.entity_id),
                },
            )
        )
        encolados += 1
    return encolados


def publicar(
    db: Session,
    *,
    tenant_id: UUID,
    entity_type: str,
    entity_id: UUID,
    body: str,
    autor_id: UUID,
    parent_id: UUID | None = None,
    menciones: list[UUID] | None = None,
) -> Comment:
    """Escribe un comentario y sus menciones, y encola los avisos.

    Todo en la misma transaccion: el llamador confirma. Un `commit` aca dejaria
    el comentario escrito y los avisos afuera si algo fallara despues — y peor,
    **cerraria la transaccion y con ella el tenant declarado** (CLAUDE.md §4),
    asi que lo que viniera despues veria cero filas.
    """
    comprobar_anclaje(db, entity_type, entity_id)
    if parent_id is not None:
        _comprobar_padre(db, parent_id, entity_id)
    mencionados = _comprobar_menciones(db, menciones or [])

    comentario = Comment(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        author_user_id=autor_id,
        body=body,
        parent_id=parent_id,
    )
    db.add(comentario)
    db.flush()

    for uid in mencionados:
        db.add(
            CommentMention(
                tenant_id=tenant_id, comment_id=comentario.id, user_id=uid
            )
        )

    autor = db.get(User, autor_id)
    _encolar_avisos(db, comentario, mencionados, autor)
    db.flush()
    return comentario


def editar(db: Session, comentario: Comment, body: str) -> Comment:
    """Cambia el texto y **deja la marca**.

    `edited_at` no es cosmetico: un comentario editado despues de que alguien
    lo respondio cambia lo que quedo escrito, y el hilo se lee como si la
    respuesta contestara al texto nuevo.
    """
    comentario.body = body
    comentario.edited_at = datetime.now(timezone.utc)
    db.flush()
    return comentario


def hilo(db: Session, entity_type: str, entity_id: UUID) -> list[Comment]:
    """Los comentarios de un registro, los raiz primero y sus respuestas debajo.

    **Las respuestas de un comentario borrado se conservan.** Ocultarlas al
    borrar la raiz haria que la decision de una persona borrara lo que
    escribieron otras. El orden las deja igual a continuacion de donde estaba
    su raiz.
    """
    comprobar_anclaje(db, entity_type, entity_id)
    todos = list(
        db.scalars(
            select(Comment)
            .where(
                Comment.entity_type == entity_type,
                Comment.entity_id == entity_id,
                Comment.deleted_at.is_(None),
            )
            .order_by(Comment.created_at)
        ).all()
    )

    respuestas: dict[UUID, list[Comment]] = {}
    raices: list[Comment] = []
    for c in todos:
        if c.parent_id is None:
            raices.append(c)
        else:
            respuestas.setdefault(c.parent_id, []).append(c)

    ordenados: list[Comment] = []
    for r in raices:
        ordenados.append(r)
        ordenados.extend(respuestas.pop(r.id, []))

    # Las respuestas cuya raiz se borro. Van al final en vez de perderse: la
    # alternativa es que desaparezcan de la pantalla sin que nadie las borrara.
    for huerfanas in respuestas.values():
        ordenados.extend(huerfanas)
    return ordenados


def mencionados_por_comentario(
    db: Session, comentarios: list[Comment]
) -> dict[UUID, list[UUID]]:
    """Quien fue mencionado en cada comentario. Una consulta, no N."""
    if not comentarios:
        return {}
    filas = db.scalars(
        select(CommentMention).where(
            CommentMention.comment_id.in_([c.id for c in comentarios])
        )
    ).all()
    por_comentario: dict[UUID, list[UUID]] = {}
    for f in filas:
        por_comentario.setdefault(f.comment_id, []).append(f.user_id)
    return por_comentario
