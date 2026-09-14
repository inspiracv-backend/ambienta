"""El buscador transversal (RF-114, #76)."""
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..deps import get_current_user, get_tenant_db
from ..models.organization import User
from ..services import buscador as svc
from ..services.permisos import tiene_permiso
from ..services.vinculos_de_documentos import ANCLAJES

router = APIRouter(prefix="/buscar", tags=["buscador"])


class CoincidenciaRead(BaseModel):
    tipo: str
    id: str
    titulo: str
    codigo: str | None
    contexto: dict[str, Any]


class GrupoRead(BaseModel):
    tipo: str
    coincidencias: list[CoincidenciaRead]
    #: `True` si el grupo se corto. Una lista cortada en silencio afirma que
    #: eso es todo lo que hay, y en un buscador esa afirmacion hace que alguien
    #: deje de buscar.
    hay_mas: bool


class ResultadoRead(BaseModel):
    grupos: list[GrupoRead]
    #: Lo que el buscador **no** mira. Hoy: el contenido de los archivos.
    advertencias: list[str]


@router.get("/", response_model=ResultadoRead, summary="Buscar en todo el sistema")
def buscar(
    q: str = Query(..., description="Que buscar. Minimo dos caracteres."),
    actual: CurrentUser | None = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """Documentos, comentarios y registros que mencionan el termino.

    **Solo devuelve lo que quien busca puede leer.** Sin esa regla el buscador
    seria un oraculo: alguien sin `audit.read` se enteraria de los titulos de
    las auditorias escribiendo una palabra en una caja. RLS acota a la empresa,
    no a lo que esa persona ve dentro de ella.

    Sin sesion identificada —el modo `X-Tenant-Id` de desarrollo— no hay de
    donde sacar permisos y no se filtra por ellos; RLS sigue acotando a la
    empresa. Mismo criterio que `/comentarios` y `/historial`.
    """
    familias: set[str] | None = None
    if actual is not None and actual.user_id:
        quien = db.scalars(
            select(User).where(
                User.clerk_id == actual.user_id, User.deleted_at.is_(None)
            )
        ).first()
        if quien is not None:
            # Se resuelve una vez y no por fila: son nueve familias.
            # Las de las fuentes MAS las de los anclajes: los comentarios
            # se filtran por la familia del registro comentado, que puede ser
            # de un tipo que no se busca directamente.
            candidatas = {svc.familia_de_fuente(f) for f in svc.FUENTES} | {
                a.familia for a in ANCLAJES.values()
            }
            familias = {
                f for f in candidatas if tiene_permiso(db, quien.id, f"{f}.read")
            }

    resultado = svc.buscar(db, q, familias_permitidas=familias)
    return ResultadoRead(
        grupos=[
            GrupoRead(
                tipo=g.tipo,
                hay_mas=g.hay_mas,
                coincidencias=[CoincidenciaRead(**vars(c)) for c in g.coincidencias],
            )
            for g in resultado.grupos
        ],
        advertencias=resultado.advertencias,
    )
