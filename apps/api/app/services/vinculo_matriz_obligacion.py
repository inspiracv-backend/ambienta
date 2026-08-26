"""El vinculo entre la Matriz Legal y las Obligaciones (RF-09, RF-14).

Cierra el gap que `openspec/analisis/seccion-d-matriz-legal.md` y
`seccion-e-obligaciones.md` dejaron anotado: *"requiere decidir como se vincula
un `Articulo` con una `Obligation`, lo cual no esta definido en ningun RF con
suficiente detalle"*.

## La decision: se cuelga de la EVALUACION, no del articulo

El vinculo es `obligations.article_compliance_id`, y no un `article_id` nuevo.
La columna ya existia en `db/01_schema.sql` con su clave foranea; lo que no
existia era nada que la escribiera ni la leyera.

Que apunte a la evaluacion y no al articulo del catalogo no es un detalle de
implementacion, es lo que hace que el vinculo signifique algo:

- **`legal_articles` es catalogo global**, compartido por todas las empresas. Un
  vinculo a esa fila no diria de quien es la obligacion.
- **La misma norma se evalua por instalacion.** El articulo 4 del DS 13
  evaluado en la planta de Antofagasta y en la de Mejillones son dos filas de
  `article_compliance`, y cada una puede generar su propia obligacion con su
  propio plazo y su propio responsable. Colgando del articulo, las dos plantas
  compartirian obligacion.
- **La evaluacion ya sabe todo lo demas.** De ella salen `matrix_norm_id` y
  `facility_id`, asi que no hace falta pedirlos ni hay forma de que se
  contradigan.

## Bidireccional es una columna leida por los dos lados

No hacen falta dos tablas ni una de union. "Las obligaciones de este articulo"
es un `WHERE article_compliance_id = X`, y "el articulo de esta obligacion" es
seguir la referencia. Una tabla de union permitiria N obligaciones por articulo
**y N articulos por obligacion**, y lo segundo no tiene sentido en el dominio:
una obligacion nace de un requisito concreto.

## Por que `matrix_norm_id` y `facility_id` NO se aceptan del cuerpo

Se derivan de la evaluacion. Si vinieran del cuerpo podrian no coincidir —una
obligacion apuntando al articulo X de la norma A mientras declara la norma B— y
nada en la base lo impediria: son tres claves foraneas independientes.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.compliance import ArticleCompliance
from ..models.obligations import Obligation

#: Prefijo de los codigos generados. Los que escribe una persona no lo llevan,
#: asi que se distingue de un vistazo cual obligacion nacio de la matriz.
PREFIJO = "MTZ"


class ErrorDeVinculo(Exception):
    """El vinculo pedido no se puede establecer."""


class EvaluacionInvisible(ErrorDeVinculo):
    """La evaluacion no existe **o es de otra empresa**, que es lo mismo.

    Las dos causas comparten excepcion a proposito. Distinguirlas seria un
    oraculo de existencia: las claves foraneas no pasan por RLS, asi que quien
    prueba identificadores al azar veria un error distinto para "no existe" que
    para "existe pero es de otro" y con eso enumeraria filas ajenas sin verlas.

    Y no era teorico: antes de este modulo, `POST /obligations/` respondia
    **422 a un id inventado y 201 a uno real de otra empresa** — o sea que la
    empresa B podia colgar su obligacion de la evaluacion de la empresa A.
    """


def _evaluacion_visible(db: Session, article_compliance_id: UUID) -> ArticleCompliance:
    """La evaluacion, leida con la sesion del tenant. Si RLS no la ve, no existe."""
    art = db.scalar(
        select(ArticleCompliance).where(
            ArticleCompliance.id == article_compliance_id,
            ArticleCompliance.deleted_at.is_(None),
        )
    )
    if art is None:
        raise EvaluacionInvisible(
            "article_compliance_id no corresponde a una evaluacion de esta empresa."
        )
    return art


def _codigo(db: Session, tenant_id: UUID) -> str:
    """Un codigo libre dentro de la empresa.

    `uq_obligations_tenant_code` es por empresa, asi que la numeracion tambien.
    Se cuenta sobre el maximo ya usado y **no sobre la cantidad de filas**: con
    borrado logico, contar filas repite un codigo apenas alguien borre una.
    """
    usados = db.scalars(
        select(Obligation.code).where(Obligation.code.like(f"{PREFIJO}-%"))
    ).all()
    numeros = [int(m.group(1)) for c in usados if (m := re.fullmatch(rf"{PREFIJO}-(\d+)", c))]
    return f"{PREFIJO}-{(max(numeros) + 1) if numeros else 1:04d}"


def crear_obligacion_desde_articulo(
    db: Session,
    *,
    article_compliance_id: UUID,
    tenant_id: UUID,
    title: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    due_at: datetime | None = None,
    owner_user_id: UUID | None = None,
) -> Obligation:
    """Crea una obligacion que nace de la evaluacion de un articulo (RF-09).

    `matrix_norm_id` y `facility_id` salen de la evaluacion. El responsable, si
    no se indica, se hereda del que ya tenia el articulo: quien responde por
    cumplirlo es normalmente quien responde por la obligacion que genera, y
    obligar a elegirlo de nuevo invita a dejarlo vacio.
    """
    art = _evaluacion_visible(db, article_compliance_id)

    obligacion = Obligation(
        tenant_id=tenant_id,
        article_compliance_id=art.id,
        matrix_norm_id=art.matrix_norm_id,
        facility_id=art.facility_id,
        code=_codigo(db, tenant_id),
        title=title or "Obligacion desde la Matriz Legal",
        period_start=period_start,
        period_end=period_end,
        due_at=due_at,
        owner_user_id=owner_user_id or art.responsible_user_id,
        status="draft",
    )
    db.add(obligacion)
    db.flush()
    db.refresh(obligacion)
    return obligacion


def vincular(db: Session, *, obligacion: Obligation, article_compliance_id: UUID) -> Obligation:
    """Ata una obligacion que ya existia a un articulo de la matriz (RF-14).

    El otro sentido del vinculo: una obligacion creada libremente que despues
    resulta responder a un requisito concreto. `matrix_norm_id` y `facility_id`
    se reescriben desde la evaluacion por la misma razon de siempre — que las
    tres referencias no puedan contradecirse.
    """
    art = _evaluacion_visible(db, article_compliance_id)

    obligacion.article_compliance_id = art.id
    obligacion.matrix_norm_id = art.matrix_norm_id
    obligacion.facility_id = art.facility_id
    db.flush()
    db.refresh(obligacion)
    return obligacion


def desvincular(db: Session, *, obligacion: Obligation) -> Obligation:
    """Suelta la obligacion de la matriz, **sin borrarla**.

    Desvincular no es deshacer: la obligacion sigue existiendo y venciendo. Lo
    que se pierde es la trazabilidad hacia el requisito que la origino, asi que
    es una operacion aparte y no un efecto de editar cualquier campo.

    `facility_id` se conserva: la planta sigue siendo la planta aunque el
    vinculo con el articulo desaparezca.
    """
    obligacion.article_compliance_id = None
    obligacion.matrix_norm_id = None
    db.flush()
    db.refresh(obligacion)
    return obligacion


def obligaciones_de_articulo(db: Session, article_compliance_id: UUID) -> list[Obligation]:
    """El sentido matriz → obligaciones.

    Valida primero que la evaluacion sea visible, en vez de devolver una lista
    vacia: sin eso, "este articulo no tiene obligaciones" y "este articulo es de
    otra empresa" se verian igual, y la pantalla mostraria un vacio tranquilo
    sobre un id que no le corresponde.
    """
    _evaluacion_visible(db, article_compliance_id)
    return list(
        db.scalars(
            select(Obligation)
            .where(
                Obligation.article_compliance_id == article_compliance_id,
                Obligation.deleted_at.is_(None),
            )
            .order_by(Obligation.due_at.nulls_last(), Obligation.code)
        ).all()
    )


def contar_por_articulo(db: Session, ids: list[UUID]) -> dict[UUID, int]:
    """Cuantas obligaciones cuelgan de cada evaluacion, en una sola consulta.

    La pantalla de detalle de norma muestra el indicador por fila. Preguntarlo
    articulo por articulo serian 210 peticiones en el DS 40, que es como se
    llega a una pantalla que tarda diez segundos sin que nadie sepa por que.
    """
    if not ids:
        return {}
    filas = db.execute(
        select(Obligation.article_compliance_id, func.count())
        .where(
            Obligation.article_compliance_id.in_(ids),
            Obligation.deleted_at.is_(None),
        )
        .group_by(Obligation.article_compliance_id)
    ).all()
    return {fila[0]: fila[1] for fila in filas}
