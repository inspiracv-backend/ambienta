"""La normativa propia de una empresa: su RCA y sus normas internas (RF-10, RF-11).

## Que faltaba, medido el 7-sep-2026

El catalogo normativo es **enteramente publico** —`legal_norms`,
`legal_norm_versions` y `legal_articles` no tenian `tenant_id` ni RLS— y esta
bien que lo sea: la ley es la misma para todos, y por eso 24 normas y 689
articulos se comparten entre empresas.

La consecuencia es que **una empresa no podia registrar su RCA**. Su Resolucion
de Calificacion Ambiental es el permiso de ESE proyecto, con condiciones que
solo la obligan a ella; escribirla en el catalogo la dejaria visible para todas
las demas — y el dano no es abstracto: las condiciones de una RCA describen la
operacion de la planta.

`db/29` agrega la columna y la politica. Este modulo es el camino para usarla.

## Lo que decide si una norma es propia

**`tenant_id`, y nada mas.** No la fuente.

Se comprobo al construir esto: `legal_sources` ya traia `RCA`, `ISO` e
`INTERNAL` desde el principio —previstas y nunca usadas— y ademas hay **una
norma publica archivada bajo la fuente RCA**: `RE-574/2019`, sobre reporte al
RETC, que es normativa general y no el permiso de nadie. O sea que
`source.code == 'RCA'` **no** significa "es de una empresa". Derivar la
propiedad de ahi habria dejado esa resolucion publica marcada como privada de
quien la mirara primero.

## Lo que este modulo NO hace

**No extrae nada de un PDF.** RF-11 la menciona como opcional y el propio
analisis la deja fuera: *"el boton Subir RCA/ISO solo agrega el registro con
articulos vacios/a completar manualmente"*. Depende de `ai-service`, que es una
carpeta vacia.

**No inventa el contenido de ninguna RCA.** Que considerandos son exigibles es
una decision que necesita RCAs reales sobre la mesa. Mismo criterio que la
`periodicidad` vacia de `retc_systems` y que el repositorio de plantillas
Excel: se construye el mecanismo, no se inventa el contenido. Una condicion
inventada en una matriz legal produce **un incumplimiento que no existe**.
"""
from __future__ import annotations

import hashlib
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.catalog import LegalArticle, LegalNorm, LegalNormVersion, LegalSource
from ..models.organization import Tenant
from .husos import hoy_de

#: Los codigos de `legal_sources` que una empresa puede usar para lo suyo.
#:
#: `BCN_LEYCHILE` no esta: esa fuente es la sincronizacion oficial, y una fila
#: escrita a mano ahi se confundiria con una importada — y peor, la proxima
#: corrida de `sincronizar-bcn` podria adoptarla o duplicarla.
FUENTES_PROPIAS = ("RCA", "ISO", "INTERNAL")


def _fuente(db: Session, codigo: str) -> LegalSource:
    if codigo not in FUENTES_PROPIAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"'{codigo}' no es una fuente para normativa propia. "
                f"Las que se admiten: {', '.join(FUENTES_PROPIAS)}."
            ),
        )
    fila = db.scalars(select(LegalSource).where(LegalSource.code == codigo)).first()
    if fila is None:  # pragma: no cover - el seed las trae
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La fuente '{codigo}' no esta en el catalogo.",
        )
    return fila


def _pais_de(db: Session, tenant_id: UUID, src: LegalSource) -> int:
    """El pais de la empresa, con el de la fuente como respaldo.

    `tenants.country_id` es lo correcto: una norma propia pertenece al pais
    donde la empresa opera. Si por algun motivo no se puede leer la empresa
    —RLS sobre `tenants` en una sesion rara— se cae al de la fuente en vez de a
    un numero escrito a mano, que seria Chile para todo el mundo.
    """
    pais = db.scalars(
        select(Tenant.country_id).where(Tenant.id == tenant_id)
    ).first()
    return pais or src.country_id


def registrar(
    db: Session,
    *,
    tenant_id: UUID,
    fuente: str,
    norm_type: str,
    title: str,
    norm_number: str | None = None,
    issuing_body: str | None = None,
    publication_date: date | None = None,
    valid_from: date | None = None,
    articulos: list[dict] | None = None,
) -> LegalNorm:
    """Registra una norma propia con su version y su articulado.

    ## Por que crea tambien una version

    `matrix_norms.selected_version_id` es `NOT NULL`, asi que sin version la
    norma no puede entrar a ninguna matriz — quedaria registrada y sin uso.

    Y no es burocracia: una RCA se modifica por resolucion posterior, y sin
    version no habria donde decir que la matriz se evaluo contra el texto de
    2019 y no contra el de 2024. Es la misma razon por la que el catalogo
    publico las tiene.

    ## Los articulos pueden venir vacios, y es lo normal

    RF-11 deja la extraccion del PDF fuera. Una RCA se carga primero como
    registro y sus considerandos se van escribiendo a mano; **cero articulos no
    es un error**, es el estado inicial. Lo que si seria un error es sembrarle
    articulos inventados para que "se vea completa".
    """
    src = _fuente(db, fuente)

    norma = LegalNorm(
        # **Lo que la hace propia.** RLS hace el resto: la politica de `db/29`
        # deja leer `tenant_id IS NULL OR = current_tenant_id()` y **escribir
        # solo lo propio**, asi que aca no hace falta comprobar nada — un
        # intento de escribir una norma publica lo rechaza Postgres.
        tenant_id=tenant_id,
        # **El pais de la EMPRESA, no el de la fuente.** La norma propia de una
        # empresa pertenece al pais donde opera; `countries` tiene cinco
        # (CL, PE, CO, MX, AR), asi que no es una constante disfrazada. La
        # primera version escribia `1` con un `hasattr` delante — o sea Chile
        # para todos, adivinando en vez de mirar el modelo.
        country_id=_pais_de(db, tenant_id, src),
        source_id=src.id,
        norm_type=norm_type,
        norm_number=norm_number,
        title=title,
        issuing_body=issuing_body,
        publication_date=publication_date,
        status="vigente",
    )
    db.add(norma)
    db.flush()

    # **`hoy_de` y no `date.today()`.** `date.today()` es "hoy donde corre este
    # proceso": la base va en UTC y el host en hora de Chile, asi que pasadas
    # las 20:00 estan en dias distintos. `countries` tiene cinco husos, y la
    # fecha desde la que rige una RCA es un dato legal. Lo marco el detector de
    # `herramientas/auditar.py`, que subio de 24 a 25 con este archivo.
    desde = valid_from or publication_date or hoy_de(db, tenant_id)
    version = LegalNormVersion(
        tenant_id=tenant_id,
        norm_id=norma.id,
        version_label="Texto cargado por la empresa",
        valid_from=desde,
        is_current=True,
        # El hash identifica el contenido y `uq_norm_versions_hash` lo exige
        # unico por norma. Con el texto vacio, dos versiones de la misma norma
        # chocarian; se deriva del titulo y la fecha para que no pase.
        content_hash=hashlib.sha256(
            f"{norma.id}|{title}|{desde.isoformat()}".encode()
        ).hexdigest(),
    )
    db.add(version)
    db.flush()

    for orden, a in enumerate(articulos or [], start=1):
        db.add(
            LegalArticle(
                tenant_id=tenant_id,
                norm_version_id=version.id,
                article_type=a.get("article_type", "article"),
                article_number=a["article_number"],
                heading=a.get("heading"),
                content=a["content"],
                display_order=a.get("display_order", orden),
            )
        )
    db.flush()
    return norma


def listar(db: Session, tenant_id: UUID) -> list[LegalNorm]:
    """Las normas propias de esta empresa. No incluye el catalogo publico.

    Se filtra por `tenant_id IS NOT NULL` **ademas** de RLS: la politica deja
    ver lo publico y lo propio junto, y esta consulta contesta otra pregunta
    —"que cargue yo"— que es la que necesita la pantalla de S-12.
    """
    return list(
        db.scalars(
            select(LegalNorm)
            .where(
                LegalNorm.tenant_id == tenant_id,
                LegalNorm.deleted_at.is_(None),
            )
            .order_by(LegalNorm.created_at.desc())
        ).all()
    )


def agregar_articulo(
    db: Session, *, tenant_id: UUID, norma: LegalNorm, datos: dict
) -> LegalArticle:
    """Un considerando mas, sobre la version vigente de una norma propia.

    Solo sobre normativa propia: los articulos del catalogo publico se
    sincronizan desde la BBN y editarlos a mano dejaria la matriz de una
    empresa evaluando un texto que no es el de la ley.
    """
    if norma.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Esa norma es del catalogo publico: su articulado se sincroniza "
                "desde la fuente oficial y no se edita a mano."
            ),
        )

    version = db.scalars(
        select(LegalNormVersion)
        .where(
            LegalNormVersion.norm_id == norma.id,
            LegalNormVersion.is_current.is_(True),
            LegalNormVersion.deleted_at.is_(None),
        )
        .order_by(LegalNormVersion.valid_from.desc())
    ).first()
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La norma no tiene una version vigente donde colgar el articulo.",
        )

    ultimo = db.scalars(
        select(LegalArticle.display_order)
        .where(LegalArticle.norm_version_id == version.id)
        .order_by(LegalArticle.display_order.desc())
    ).first()

    articulo = LegalArticle(
        tenant_id=tenant_id,
        norm_version_id=version.id,
        article_type=datos.get("article_type", "article"),
        article_number=datos["article_number"],
        heading=datos.get("heading"),
        content=datos["content"],
        display_order=datos.get("display_order", (ultimo or 0) + 1),
    )
    db.add(articulo)
    db.flush()
    return articulo
