"""El buscador transversal (RF-114, #76).

## Que problema resuelve

Los tres cambios anteriores de la epica #31 repartieron la informacion: un
documento cuelga de una obligacion (#73), la conversacion vive en el registro
(#74), la historia se reune por entidad (#75). Todo eso se encuentra **si ya
sabes a que ficha entrar**.

La pregunta de un fiscalizador no tiene esa forma. Dice *"muestreme lo de los
residuos peligrosos"*, y eso esta repartido entre una norma, tres obligaciones,
un procedimiento y el comentario donde alguien explico por que se declaro tarde.

## Por que FTS y no `ILIKE`, medido

Este repositorio ya perdio tiempo con esto en la BCN: *"la busqueda distingue
acentos — `emision` no encuentra `EMISION` con tilde: devuelve cero resultados
y ningun error"*. Medido el 7-sep contra la base real:

| forma | `emision` encuentra `DECRETO DE EMISION` (con tilde) |
|---|---|
| `to_tsvector('spanish', ...)` | **si** |
| `ILIKE '%emision%'` | **no** |

El stemmer espanol normaliza los acentos por su cuenta, asi que no hace falta
`unaccent`. Y `ILIKE` —la opcion corta— fallaria sobre **13 de las 24 normas
del catalogo**, que es justo donde estan los titulos en mayuscula con tilde.
Cero resultados y ningun error, otra vez.

## El permiso es el problema real, no la consulta

Un buscador que devuelve de todo **es un oraculo**: quien no tiene `audit.read`
no deberia enterarse de los titulos de las auditorias escribiendo una palabra
en una caja. RLS acota a la empresa, no a lo que esa persona puede ver dentro
de ella.

Por eso el filtro va **antes** de consultar y no despues: el resultado seria el
mismo, pero asi el codigo dice que el permiso decide **que se busca**.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from ..models.audit import Audit, Nonconformity
from ..models.catalog import LegalNorm
from ..models.comentarios import Comment
from ..models.documents import Document
from ..models.iso14001 import EnvironmentalAspect, RegulatedEquipment, RiskOpportunity
from ..models.obligations import Obligation
from ..models.organization import Process
from .vinculos_de_documentos import ANCLAJES

#: Minimo de caracteres. Una letra sola devuelve casi todo, que no es una
#: busqueda: es un listado caro disfrazado. Se responde 422 **explicando el
#: minimo** en vez de una lista vacia, que se leeria como "no hay nada".
MINIMO = 2

#: Tope por grupo. Un grupo cortado lo dice: una lista que se corta en silencio
#: afirma que eso es todo lo que hay, y en un buscador esa afirmacion es la que
#: hace que alguien deje de buscar.
TOPE_POR_GRUPO = 10


@dataclass
class Fuente:
    """Una tabla en la que se busca, y con que permiso."""

    #: La etiqueta que devuelve la API. Coincide con la clave de `ANCLAJES`
    #: cuando la entidad es anclable, para que el frontend use un vocabulario
    #: solo (el de dominio) — la leccion de RF-113.
    tipo: str
    modelo: type[Any]
    #: Columnas de texto libre: van por FTS en espanol, que resuelve acentos.
    texto: tuple[str, ...]
    #: Columnas de codigo o numero: van por `ILIKE`. "19.300" no es una palabra
    #: que el stemmer sepa tratar, y quien la escribe quiere coincidencia
    #: literal.
    codigos: tuple[str, ...] = ()
    #: La familia de permisos. `None` significa que sale de `ANCLAJES`.
    familia: str | None = None


FUENTES: tuple[Fuente, ...] = (
    # Los documentos no son un anclaje —se adjuntan A las cosas— asi que su
    # familia va explicita.
    Fuente("document", Document, ("title",), ("code",), familia="document"),
    Fuente("obligation", Obligation, ("title",), ("code",)),
    Fuente("legal_norm", LegalNorm, ("title",), ("norm_number",)),
    Fuente("nonconformity", Nonconformity, ("title",), ("code",)),
    Fuente("audit", Audit, ("title",), ("code",)),
    # **Las columnas salen del modelo real, no de lo que uno supone.** La
    # primera version de esta lista decia `name` para el aspecto, `title` para
    # el riesgo y `code` para el equipo: ninguna de las tres existe. Un
    # `getattr` sobre una columna inventada no falla al arrancar — falla al
    # buscar, o peor, devuelve cero y se lee como "no hay coincidencias".
    #
    # El aspecto se busca por lo que ES y por la actividad que lo genera: quien
    # busca "residuos" puede estar pensando en cualquiera de las dos.
    Fuente("environmental_aspect", EnvironmentalAspect, ("aspect", "activity")),
    Fuente("risk_opportunity", RiskOpportunity, ("description",), ("code",)),
    Fuente(
        "regulated_equipment",
        RegulatedEquipment,
        ("name",),
        # El equipo no tiene `code`: lo que se cita ante un fiscalizador es su
        # numero de inscripcion ante la autoridad.
        ("registration_number",),
    ),
    Fuente("process", Process, ("name",), ("code",)),
)


@dataclass
class Coincidencia:
    tipo: str
    id: str
    titulo: str
    #: El codigo, cuando la entidad tiene. Es lo que se cita en una auditoria.
    codigo: str | None = None
    #: Para un comentario: sobre que registro se dijo.
    contexto: dict[str, Any] = field(default_factory=dict)


@dataclass
class Grupo:
    tipo: str
    coincidencias: list[Coincidencia]
    #: `True` si se alcanzo el tope y hay mas sin devolver.
    hay_mas: bool = False


@dataclass
class Resultado:
    grupos: list[Grupo]
    #: **No se busca dentro de los archivos.** El PDF vive en B2 y extraerle
    #: texto es otra cosa. Se declara para que nadie concluya que un
    #: procedimiento no menciona algo: se busco su ficha, no su contenido.
    advertencias: list[str] = field(
        default_factory=lambda: [
            "No se busca dentro del contenido de los archivos adjuntos, "
            "solo en su titulo y su codigo."
        ]
    )


def familia_de_fuente(fuente: Fuente) -> str:
    """La familia de permisos de esta fuente.

    Sale de `ANCLAJES` salvo que la fuente la declare — o sea, del **mismo
    mapa** que valida el anclaje de RF-108, resuelve el permiso de RF-111 y
    traduce el vocabulario de RF-113. Es su cuarto uso y sigue siendo una sola
    lista: agregar una entidad buscable no obliga a mantener un diccionario
    paralelo de permisos.
    """
    if fuente.familia is not None:
        return fuente.familia
    return ANCLAJES[fuente.tipo].familia


def _condicion(modelo: type[Any], fuente: Fuente, q: str):
    """FTS para los titulos, `ILIKE` para los codigos."""
    partes = []
    for col in fuente.texto:
        partes.append(
            func.to_tsvector("spanish", getattr(modelo, col)).op("@@")(
                func.plainto_tsquery("spanish", q)
            )
        )
    for col in fuente.codigos:
        partes.append(cast(getattr(modelo, col), String).ilike(f"%{q}%"))
    return or_(*partes)


def buscar(
    db: Session, q: str, *, familias_permitidas: set[str] | None = None
) -> Resultado:
    """Busca `q` en documentos, comentarios y registros.

    `familias_permitidas` a `None` significa **no filtrar por permiso**, y es
    lo que corresponde en el modo `X-Tenant-Id` —desarrollo, sin Clerk—: no hay
    de donde sacar permisos y RLS ya acota a la empresa. Es el mismo criterio
    que `/comentarios` y `/historial`, y se dice aca para que no se lea como un
    hueco.
    """
    q = (q or "").strip()
    if len(q) < MINIMO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La busqueda necesita al menos {MINIMO} caracteres.",
        )

    grupos: list[Grupo] = []

    def permitida(familia: str) -> bool:
        return familias_permitidas is None or familia in familias_permitidas

    for fuente in FUENTES:
        if not permitida(familia_de_fuente(fuente)):
            # No se consulta lo que la persona no puede leer. Filtrar despues
            # daria el mismo resultado; filtrar antes deja dicho que el permiso
            # decide **que se busca**.
            continue

        modelo = fuente.modelo
        condiciones = [_condicion(modelo, fuente, q)]
        if hasattr(modelo, "deleted_at"):
            condiciones.append(modelo.deleted_at.is_(None))

        filas = db.scalars(
            select(modelo).where(*condiciones).limit(TOPE_POR_GRUPO + 1)
        ).all()
        if not filas:
            continue

        hay_mas = len(filas) > TOPE_POR_GRUPO
        coincidencias = [
            Coincidencia(
                tipo=fuente.tipo,
                id=str(f.id),
                titulo=str(
                    getattr(f, fuente.texto[0], None) or "(sin titulo)"
                ),
                codigo=(
                    str(getattr(f, fuente.codigos[0]))
                    if fuente.codigos and getattr(f, fuente.codigos[0], None)
                    else None
                ),
            )
            for f in filas[:TOPE_POR_GRUPO]
        ]
        grupos.append(Grupo(tipo=fuente.tipo, coincidencias=coincidencias, hay_mas=hay_mas))

    # ── Los comentarios ──────────────────────────────────────────────────
    #
    # Caso aparte: su permiso depende del registro comentado, que varia fila
    # por fila. Se acota en el mismo `WHERE` a los `entity_type` cuya familia
    # la persona puede leer, en vez de traer todo y descartar despues.
    tipos_visibles = [
        t for t, a in ANCLAJES.items() if permitida(a.familia)
    ]
    if tipos_visibles:
        condiciones = [
            func.to_tsvector("spanish", Comment.body).op("@@")(
                func.plainto_tsquery("spanish", q)
            ),
            Comment.deleted_at.is_(None),
            Comment.entity_type.in_(tipos_visibles),
        ]
        filas = db.scalars(
            select(Comment)
            .where(*condiciones)
            .order_by(Comment.created_at.desc())
            .limit(TOPE_POR_GRUPO + 1)
        ).all()
        if filas:
            grupos.append(
                Grupo(
                    tipo="comment",
                    hay_mas=len(filas) > TOPE_POR_GRUPO,
                    coincidencias=[
                        Coincidencia(
                            tipo="comment",
                            id=str(c.id),
                            # Un extracto, no el comentario entero: la lista de
                            # resultados no es donde se lee una conversacion.
                            titulo=(c.body[:200] + ("…" if len(c.body) > 200 else "")),
                            contexto={
                                "entity_type": c.entity_type,
                                "entity_id": str(c.entity_id),
                            },
                        )
                        for c in filas[:TOPE_POR_GRUPO]
                    ],
                )
            )

    return Resultado(grupos=grupos)
