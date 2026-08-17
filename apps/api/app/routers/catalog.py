from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud.catalog import (
    crud_country,
    crud_legal_norm,
    crud_legal_source,
    crud_sector,
)
from ..models.catalog import LegalArticle, LegalNormVersion
from ..auth import CurrentUser
from ..deps import exigir_admin_global, get_db
from ..schemas.catalog import (
    CountryRead,
    LegalArticleRead,
    LegalNormCreate,
    LegalNormRead,
    LegalNormUpdate,
    LegalSourceCreate,
    LegalSourceRead,
    LegalSourceUpdate,
    SectorCreate,
    SectorRead,
    SectorUpdate,
)
from ._comun import borrar_o_404, obtener_o_404

router = APIRouter(prefix="/catalog", tags=["catalog"])


# ── Paises ────────────────────────────────────────────────────────────────
#
# Solo lectura, y es una decision escrita: "catalogo estatico de referencia, se
# consulta, no se administra" (docs/estado-crud-base-de-datos.md).
#
# Lo que faltaba era la mitad positiva de esa decision. Estaba cumplida la parte
# negativa —no hay escritura— y omitida la otra: sin GET, `POST /catalog/norms`
# exigia un `country_id` que la interfaz no tenia de donde sacar, asi que crear
# una norma desde la aplicacion era imposible.
#
# No lleva `exigir_admin_global`: es el catalogo de paises, la misma lista para
# todo el mundo. Pedirlo restringido no protegeria nada y romperia la pantalla
# de quien no es admin, que es justo quien necesita elegir el pais.


@router.get("/countries", response_model=list[CountryRead])
def list_countries(db: Session = Depends(get_db)):
    return crud_country.get_multi(db)


@router.get("/countries/{country_id}", response_model=CountryRead)
def get_country(country_id: int, db: Session = Depends(get_db)):
    return obtener_o_404(crud_country, db, country_id, recurso="Country")



@router.get("/sources", response_model=list[LegalSourceRead])
def list_sources(db: Session = Depends(get_db)):
    return crud_legal_source.get_multi(db)


@router.get("/sectors", response_model=list[SectorRead])
def list_sectors(db: Session = Depends(get_db)):
    return crud_sector.get_multi(db)


@router.get("/norms", response_model=list[LegalNormRead])
def list_norms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_legal_norm.get_multi(db, skip=skip, limit=limit)


@router.get("/norms/{norm_id}", response_model=LegalNormRead)
def get_norm(norm_id: UUID, db: Session = Depends(get_db)):
    obj = crud_legal_norm.get(db, norm_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Norm not found")
    return obj


@router.get("/norms/{norm_id}/articles", response_model=list[LegalArticleRead])
def list_norm_articles(norm_id: UUID, db: Session = Depends(get_db)):
    """Articulos del texto **vigente** de la norma.

    El articulo no cuelga de la norma sino de una VERSION suya, porque el texto
    legal cambia y una auditoria pregunta bajo que redaccion se evaluo en una
    fecha dada. Aca se devuelve la version marcada `is_current`: es la que
    corresponde evaluar hoy.

    Una norma sin version vigente devuelve lista vacia, no 404: la norma existe
    y la respuesta correcta es "no hay articulos que evaluar todavia".
    """
    if not crud_legal_norm.get(db, norm_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Norm not found")

    vigente = db.scalar(
        select(LegalNormVersion.id).where(
            LegalNormVersion.norm_id == norm_id,
            LegalNormVersion.is_current.is_(True),
            LegalNormVersion.deleted_at.is_(None),
        )
    )
    if vigente is None:
        return []

    return db.scalars(
        select(LegalArticle)
        .where(
            LegalArticle.norm_version_id == vigente,
            LegalArticle.deleted_at.is_(None),
        )
        .order_by(LegalArticle.display_order)
    ).all()


# ── Escritura del catalogo ────────────────────────────────────────────────
#
# ADVERTENCIA que vale para todo lo de abajo: este catalogo se SINCRONIZA
# desde la BCN. Una edicion manual la puede pisar la proxima corrida del
# sincronizador. Se expone porque administrar el catalogo es una funcion real
# del Admin Global —corregir una norma mal importada, dar de alta una fuente—
# pero no es el camino normal de mantenimiento.
#
# Escribir exige Admin Global: la ley es la misma para todas las empresas, asi
# que un cambio aca las afecta a todas.

@router.post("/sources", response_model=LegalSourceRead, status_code=status.HTTP_201_CREATED)
def create_source(data: LegalSourceCreate, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    obj = crud_legal_source.create(db, obj_in=data)
    db.commit()
    return obj


@router.get("/sources/{source_id}", response_model=LegalSourceRead)
def get_source(source_id: int, db: Session = Depends(get_db)):
    return obtener_o_404(crud_legal_source, db, source_id, recurso="LegalSource")


@router.patch("/sources/{source_id}", response_model=LegalSourceRead)
def update_source(source_id: int, data: LegalSourceUpdate, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    obj = obtener_o_404(crud_legal_source, db, source_id, recurso="LegalSource")
    obj = crud_legal_source.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    borrar_o_404(crud_legal_source, db, source_id, recurso="LegalSource")


@router.post("/sectors", response_model=SectorRead, status_code=status.HTTP_201_CREATED)
def create_sector(data: SectorCreate, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    obj = crud_sector.create(db, obj_in=data)
    db.commit()
    return obj


@router.get("/sectors/{sector_id}", response_model=SectorRead)
def get_sector(sector_id: int, db: Session = Depends(get_db)):
    return obtener_o_404(crud_sector, db, sector_id, recurso="Sector")


@router.patch("/sectors/{sector_id}", response_model=SectorRead)
def update_sector(sector_id: int, data: SectorUpdate, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    obj = obtener_o_404(crud_sector, db, sector_id, recurso="Sector")
    obj = crud_sector.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/sectors/{sector_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sector(sector_id: int, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    borrar_o_404(crud_sector, db, sector_id, recurso="Sector")


@router.post("/norms", response_model=LegalNormRead, status_code=status.HTTP_201_CREATED)
def create_norm(data: LegalNormCreate, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    obj = crud_legal_norm.create(db, obj_in=data)
    db.commit()
    return obj


@router.patch("/norms/{norm_id}", response_model=LegalNormRead)
def update_norm(norm_id: UUID, data: LegalNormUpdate, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    obj = obtener_o_404(crud_legal_norm, db, norm_id, recurso="LegalNorm")
    obj = crud_legal_norm.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/norms/{norm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_norm(norm_id: UUID, _: CurrentUser = Depends(exigir_admin_global), db: Session = Depends(get_db)):
    """Retira una norma del catalogo. Las matrices que la referencian no se
    tocan: registran que esa norma le aplico a la empresa en su momento."""
    borrar_o_404(crud_legal_norm, db, norm_id, recurso="LegalNorm")
