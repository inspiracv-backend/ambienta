"""La normativa propia de una empresa (RF-10, RF-11, bloque D).

Va bajo `/compliance` y no bajo `/catalog` a proposito: el catalogo es lo
**compartido** —y su router responde a `get_db`, sin tenant— mientras que una
RCA es de una empresa. Colgarla del catalogo haria que la ruta dijera lo
contrario de lo que la fila significa.

Ademas asi hereda la familia de permisos `legal_matrix`, que es la correcta:
cargar la RCA de la empresa es trabajo de su matriz legal.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_tenant_db, get_tenant_id
from ..models.catalog import LegalArticle, LegalNorm, LegalNormVersion
from ._comun import obtener_o_404
from ..crud.catalog import crud_legal_norm
from ..schemas.catalog import LegalArticleRead
from ..services import normativa_propia as svc

router = APIRouter(prefix="/compliance/normativa-propia", tags=["compliance"])


class ArticuloEntrada(BaseModel):
    article_number: str = Field(max_length=40)
    content: str
    heading: str | None = None
    article_type: str = "article"


class NormaPropiaCreate(BaseModel):
    #: `RCA`, `ISO` o `INTERNAL`. `BCN_LEYCHILE` no se admite: esa fuente es la
    #: sincronizacion oficial, y una fila escrita a mano ahi se confundiria con
    #: una importada.
    fuente: str
    norm_type: str = Field(max_length=80)
    title: str
    norm_number: str | None = Field(default=None, max_length=60)
    issuing_body: str | None = Field(default=None, max_length=240)
    publication_date: date | None = None
    valid_from: date | None = None
    #: **Pueden venir vacios, y es lo normal.** RF-11 deja la extraccion del PDF
    #: fuera; una RCA se carga primero como registro y sus considerandos se
    #: escriben despues. Cero articulos no es un error.
    articulos: list[ArticuloEntrada] = Field(default_factory=list)


class NormaPropiaRead(BaseModel):
    id: UUID
    tenant_id: UUID | None
    source_id: int
    norm_type: str
    norm_number: str | None
    title: str
    issuing_body: str | None
    publication_date: date | None
    articulos: int


def _armar(db: Session, normas: list[LegalNorm]) -> list[NormaPropiaRead]:
    """Con el conteo de articulos, en dos consultas y no en 2N.

    El conteo se **deriva**, no se guarda: un numero escrito seria la forma mas
    corta de que la ficha y el articulado digan cosas distintas.
    """
    conteo: dict[UUID, int] = {}
    if normas:
        filas = db.execute(
            select(LegalNormVersion.norm_id, LegalArticle.id)
            .join(LegalArticle, LegalArticle.norm_version_id == LegalNormVersion.id)
            .where(
                LegalNormVersion.norm_id.in_([n.id for n in normas]),
                LegalArticle.deleted_at.is_(None),
            )
        ).all()
        for norm_id, _ in filas:
            conteo[norm_id] = conteo.get(norm_id, 0) + 1

    return [
        NormaPropiaRead(
            id=n.id,
            tenant_id=n.tenant_id,
            source_id=n.source_id,
            norm_type=n.norm_type,
            norm_number=n.norm_number,
            title=n.title,
            issuing_body=n.issuing_body,
            publication_date=n.publication_date,
            articulos=conteo.get(n.id, 0),
        )
        for n in normas
    ]


@router.get("/", response_model=list[NormaPropiaRead], summary="Normativa propia de la empresa")
def listar(
    tenant_id: UUID = Depends(get_tenant_id), db: Session = Depends(get_tenant_db)
):
    """Sólo lo que cargó esta empresa. El catálogo público va en `/catalog`."""
    return _armar(db, svc.listar(db, tenant_id))


@router.post(
    "/",
    response_model=NormaPropiaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una norma propia (RCA o ISO)",
)
def registrar(
    data: NormaPropiaCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Registra la norma, su versión vigente y su articulado.

    **No extrae nada de un PDF.** RF-11 lo deja como opcional y depende de
    `ai-service`, que es una carpeta vacía.
    """
    norma = svc.registrar(
        db,
        tenant_id=tenant_id,
        fuente=data.fuente,
        norm_type=data.norm_type,
        title=data.title,
        norm_number=data.norm_number,
        issuing_body=data.issuing_body,
        publication_date=data.publication_date,
        valid_from=data.valid_from,
        articulos=[a.model_dump() for a in data.articulos],
    )
    salida = _armar(db, [norma])[0]
    db.commit()
    return salida


@router.get(
    "/{norma_id}/articulos",
    response_model=list[LegalArticleRead],
    summary="Los considerandos de una norma propia",
)
def leer_articulos(
    norma_id: UUID,
    db: Session = Depends(get_tenant_db),
):
    """El articulado de una RCA o una ISO de la empresa.

    La lista de normas propias devuelve un **conteo**, así que la pantalla de
    S-12 podía decir «3 considerandos» sin que hubiera forma de ver cuáles.

    Hoy el catálogo público también los devuelve al dueño, pero **por un efecto
    de borde de las dependencias de FastAPI y no por diseño** — está explicado
    en `services/normativa_propia.py::articulos_de`. Esta ruta cuelga de
    `get_tenant_db` explícito: la normativa propia es de una empresa, y quien la
    lee tiene que declararlo.

    Devuelve el mismo esquema que el articulado del catálogo público, a
    propósito: quien lo consuma no debería necesitar dos mapeos para lo que en
    la pantalla es la misma lista.
    """
    norma = obtener_o_404(crud_legal_norm, db, norma_id, recurso="LegalNorm")
    return svc.articulos_de(db, norma)


@router.post(
    "/{norma_id}/articulos",
    response_model=NormaPropiaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar un considerando a una norma propia",
)
def agregar_articulo(
    norma_id: UUID,
    data: ArticuloEntrada,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Un considerando más sobre la versión vigente.

    El articulado del catálogo público **no** se edita por acá: se sincroniza
    desde la fuente oficial, y tocarlo a mano dejaría la matriz de una empresa
    evaluando un texto que no es el de la ley.
    """
    norma = obtener_o_404(crud_legal_norm, db, norma_id, recurso="LegalNorm")
    svc.agregar_articulo(db, tenant_id=tenant_id, norma=norma, datos=data.model_dump())
    salida = _armar(db, [norma])[0]
    db.commit()
    return salida
