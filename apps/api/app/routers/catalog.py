from datetime import datetime, timezone
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
from ..models.catalog import LegalArticle, LegalNormVersion, NormSector, Sector
from ..models.organization import User
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
    NormSectorRead,
    NormSectorWrite,
    SectorRead,
    SectorUpdate,
)
from ._comun import borrar_o_404, obtener_o_404

router = APIRouter(prefix="/catalog", tags=["catalog"])

# El CHECK vive en la base; esto lo repite para poder dar un 422 con el detalle
# en vez de un 500 por violacion de restriccion.
NIVELES_DE_APLICABILIDAD = {"directa", "indirecta", "referencial"}


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


# ── Clasificacion de normas por sector (RF-19) ────────────────────────────
#
# Es lo que **alimenta** el filtro. Sin estas filas, calcular la normativa de
# una empresa devuelve vacio — y eso no significa que no tenga obligaciones,
# significa que nadie clasifico todavia.
#
# Leer no exige nada: saber que normas aplican a un sector es informacion de
# trabajo. **Escribir exige Admin Global**, porque `norm_sectors` no lleva
# `tenant_id`: una clasificacion errada se propaga a TODAS las empresas de ese
# sector, no solo a la de quien la escribio.


@router.get("/norms/{norm_id}/sectors", response_model=list[NormSectorRead])
def list_norm_sectors(norm_id: UUID, db: Session = Depends(get_db)):
    """A que sectores aplica esta norma, con que nivel y por que."""
    if not crud_legal_norm.get(db, norm_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Norm not found")

    return db.scalars(
        select(NormSector).where(NormSector.norm_id == norm_id)
    ).all()


@router.put(
    "/norms/{norm_id}/sectors/{sector_id}",
    response_model=NormSectorRead,
    tags=["business-logic"],
)
def set_norm_sector(
    norm_id: UUID,
    sector_id: int,
    data: NormSectorWrite,
    user: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    """Declara que una norma aplica a un sector.

    Es `PUT` y no `POST` porque la operacion es idempotente: declarar dos veces
    lo mismo deja el mismo estado.

    **El nivel decide si es obligatoria o recomendada.** `directa` significa que
    la empresa del sector la debe cumplir; `indirecta` y `referencial` que se le
    recomienda revisarla. Es la distincion que pidio el negocio, y por eso el
    campo no admite texto libre.

    Se registra quien clasifico y cuando: un error con nombre y fundamento se
    corrige, uno anonimo se discute sin llegar a nada.
    """
    if not crud_legal_norm.get(db, norm_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Norm not found")
    if db.get(Sector, sector_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sector not found")
    if data.applicability_level not in NIVELES_DE_APLICABILIDAD:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Nivel invalido: '{data.applicability_level}'. "
                f"Valores validos: {', '.join(sorted(NIVELES_DE_APLICABILIDAD))}."
            ),
        )

    fila = db.get(NormSector, (norm_id, sector_id))
    if fila is None:
        fila = NormSector(norm_id=norm_id, sector_id=sector_id)
        db.add(fila)
    fila.applicability_level = data.applicability_level
    fila.rationale = data.rationale
    fila.article_id = data.article_id
    # Lo declaro una persona, no un proceso. `confidence` queda en NULL: no
    # tiene sentido una probabilidad cuando alguien lo afirma.
    fila.source = "analyst"
    fila.classified_at = datetime.now(timezone.utc)
    autor = db.scalar(select(User).where(User.clerk_id == user.user_id))
    fila.classified_by = autor.id if autor else None
    db.commit()
    db.refresh(fila)
    return fila


@router.delete(
    "/norms/{norm_id}/sectors/{sector_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def clear_norm_sector(
    norm_id: UUID,
    sector_id: int,
    _: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    """Retira la clasificacion de una norma en un sector.

    Las empresas que ya la tengan en su matriz **no la pierden**: lo que se quita
    es la regla que la haria entrar de ahora en mas.
    """
    fila = db.get(NormSector, (norm_id, sector_id))
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esa norma no esta clasificada en ese sector.",
        )
    db.delete(fila)
    db.commit()


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
