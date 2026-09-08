"""La conversacion sobre cualquier registro (RF-111, RF-112, #74).

**Un router y no uno por entidad.** El comentario es polimorfico igual que el
vinculo documental: `entity_type` dice sobre que se comenta. La alternativa
—`/obligations/{id}/comentarios` y su equivalente en cada router— serian trece
copias de la misma logica, y trece lugares donde olvidar la comprobacion del
anclaje el dia que se agregue el catorce.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..deps import get_current_user, get_tenant_db, get_tenant_id
from ..models.comentarios import Comment
from ..models.organization import User
from ..schemas.comentarios import ComentarioCreate, ComentarioRead, ComentarioUpdate
from ..services import comentarios as svc
from ..services.permisos import tiene_permiso
from ..services.vinculos_de_documentos import familia_de

router = APIRouter(prefix="/comentarios", tags=["comentarios"])


def _quien(db: Session, actual: CurrentUser | None) -> User | None:
    """El usuario de la sesion, o `None` si no hay. No exige nada."""
    if actual is None or not actual.user_id:
        return None
    return db.scalars(
        select(User).where(User.clerk_id == actual.user_id, User.deleted_at.is_(None))
    ).first()


def _autor(db: Session, actual: CurrentUser | None) -> User:
    """Quien escribe, o 409.

    **No se toma al primer administrador de la empresa.** Esa es la salida
    comoda y deja escrito que esa persona dijo algo que no dijo — en un
    registro que se exporta a un auditor. Mismo criterio que aprobar una
    revision documental.

    El costo es que en el modo `X-Tenant-Id` —sin Clerk— no se puede comentar.
    Es deliberado.
    """
    if actual is None or not actual.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Un comentario necesita una sesion identificada: no se puede "
                "atribuir a nadie sin saber quien lo escribe."
            ),
        )
    fila = db.scalars(
        select(User).where(User.clerk_id == actual.user_id, User.deleted_at.is_(None))
    ).first()
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La sesion no corresponde a un usuario de esta empresa.",
        )
    return fila


def _armar(db: Session, filas: list[Comment]) -> list[ComentarioRead]:
    """Resuelve el nombre del autor y las menciones en dos consultas, no en 2N."""
    menciones = svc.mencionados_por_comentario(db, filas)
    nombres = {
        u.id: u.full_name
        for u in db.scalars(
            select(User).where(User.id.in_([f.author_user_id for f in filas]))
        ).all()
    } if filas else {}
    return [
        ComentarioRead(
            **{c: getattr(f, c) for c in (
                "id", "tenant_id", "entity_type", "entity_id", "author_user_id",
                "body", "parent_id", "edited_at", "created_at",
            )},
            author_name=nombres.get(f.author_user_id),
            menciones=menciones.get(f.id, []),
        )
        for f in filas
    ]


def _exigir(db: Session, autor: User, entity_type: str, accion: str) -> None:
    """El permiso depende **del registro sobre el que se comenta**.

    Comentar sobre una auditoria exige `audit.write`; sobre una obligacion,
    `obligation.write`. No hay una familia `comment` propia y es deliberado: un
    permiso nuevo que ningun rol concede es un 403 para todos, y el sintoma
    —"no puedo comentar"— no se parece en nada a la causa. Es la misma leccion
    que dejo el CRM al reusar `manager`.

    Y hace falta: sin esto el rol `servicio_lectura` —que solo tiene lecturas—
    podria escribir comentarios en cualquier ficha de la empresa.

    La guarda derivada de la ruta (`exigir_permiso_de_la_ruta`) no sirve aca
    porque el permiso sale del **cuerpo**, no del camino: una sola ruta cubre
    trece entidades.
    """
    codigo = f"{familia_de(entity_type)}.{accion}"
    if not tiene_permiso(db, autor.id, codigo):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Falta el permiso {codigo}.",
        )


@router.get("/", response_model=list[ComentarioRead], summary="Hilo de un registro")
def leer_hilo(
    entity_type: str = Query(...),
    entity_id: UUID = Query(...),
    actual: CurrentUser | None = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """Los comentarios de un registro: cada raiz con sus respuestas debajo.

    Leer exige `<familia>.read` **cuando hay sesion identificada**. Sin ella
    —el modo `X-Tenant-Id` de desarrollo— no hay de donde sacar permisos y RLS
    ya acota las filas a la empresa; es el mismo criterio que el resto de la
    API en ese modo.
    """
    quien = _quien(db, actual)
    if quien is not None:
        _exigir(db, quien, entity_type, "read")
    return _armar(db, svc.hilo(db, entity_type, entity_id))


@router.post(
    "/",
    response_model=ComentarioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Comentar sobre un registro",
)
def comentar(
    data: ComentarioCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    actual: CurrentUser | None = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """Publica un comentario, registra las menciones y encola sus avisos."""
    autor = _autor(db, actual)
    _exigir(db, autor, data.entity_type, "write")
    comentario = svc.publicar(
        db,
        tenant_id=tenant_id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        body=data.body,
        autor_id=autor.id,
        parent_id=data.parent_id,
        menciones=data.menciones,
    )
    # Se arma **antes** del commit: despues la transaccion esta cerrada y con
    # ella se va el tenant declarado, asi que las consultas verian cero filas
    # (CLAUDE.md §4).
    salida = _armar(db, [comentario])[0]
    db.commit()
    return salida


def _mio_o_404(db: Session, comentario_id: UUID, autor: User) -> Comment:
    """El comentario, si es de esta empresa y lo escribio quien pide.

    **Editar el comentario de otro es cambiar lo que esa persona dijo**, y en
    un registro de cumplimiento eso no lo arregla un permiso: no hay ningun
    caso legitimo. Un administrador que necesite quitar algo lo borra, y el
    borrado queda en el registro de actividades.
    """
    fila = db.scalars(
        select(Comment).where(Comment.id == comentario_id, Comment.deleted_at.is_(None))
    ).first()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if fila.author_user_id != autor.id:
        # 404 y no 403: distinguirlos diria que ese comentario existe.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return fila


@router.patch(
    "/{comentario_id}", response_model=ComentarioRead, summary="Editar un comentario propio"
)
def editar(
    comentario_id: UUID,
    data: ComentarioUpdate,
    actual: CurrentUser | None = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """Cambia el texto y deja la marca de edicion, que se muestra."""
    autor = _autor(db, actual)
    fila = _mio_o_404(db, comentario_id, autor)
    _exigir(db, autor, fila.entity_type, "write")
    comentario = svc.editar(db, fila, data.body)
    salida = _armar(db, [comentario])[0]
    db.commit()
    return salida


@router.delete(
    "/{comentario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirar un comentario propio",
)
def borrar(
    comentario_id: UUID,
    actual: CurrentUser | None = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """Borrado logico. **Las respuestas se conservan**: eliminarlas haria que la
    decision de una persona borrara lo que escribieron otras."""
    from datetime import datetime, timezone

    autor = _autor(db, actual)
    comentario = _mio_o_404(db, comentario_id, autor)
    _exigir(db, autor, comentario.entity_type, "write")
    comentario.deleted_at = datetime.now(timezone.utc)
    db.commit()
