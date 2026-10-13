"""Los catalogos del registro de mejora, y lo que hacen cumplir (#41, RF-100).

## Por que existen

La escala de severidad era un CHECK con `minor | major | critical`: la misma
para todas las empresas y solo en ingles. El cliente dice `Alta` y `Mayor`, y el
siguiente dira otra cosa. Sin catalogo, el segundo cliente obliga a un cambio de
esquema (design.md §4, decision S-14).

## Y por que no es solo una tabla de etiquetas

Un catalogo que nadie consulta es exactamente el patron que este repositorio ya
conoce: `bcn.sincronizar()`, `control_documental.py`, la mitad del CRM — codigo
escrito, probado y sin un solo llamador. Estos dos hacen dos cosas concretas:

1. **`comprobar_severidad`** rechaza un nivel que la empresa desactivo o borro.
   El CHECK de la columna sigue vigente y sigue siendo la barrera de la base;
   esto es la barrera de la empresa, que es mas estrecha. Una que decidio no
   usar `critical` deja de poder registrar hallazgos criticos.

2. **`fecha_limite`** calcula `nonconformities.due_date` desde el plazo del
   nivel. Esa columna existe desde el principio y **nadie la calculaba**: se
   aceptaba del cuerpo o se dejaba vacia, o sea que "una critica se cierra en 15
   dias" era una regla que la empresa tenia en la cabeza y el sistema no
   aplicaba.

## El plazo en NULL no es cero

`days_to_close` nace vacio en todas las empresas, a proposito. Sembrar 60/30/15
seria inventarles el compromiso, y **un plazo falso en un sistema de
cumplimiento es peor que ninguno**: produce una fecha limite que nadie acordo y
la empresa cree que va a tiempo. Mismo criterio que la `periodicidad` vacia de
`retc_systems` y que el repositorio de plantillas Excel.

Mientras este en NULL, `due_date` se sigue pidiendo a mano, igual que hasta hoy.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.audit import ImprovementMethodology, ImprovementSeverity

#: Lo que se siembra en una empresa nueva.
#:
#: **Tiene que coincidir con `db/25_catalogos_de_mejora.sql`**, y hay una prueba
#: que lee ese archivo y lo exige. Dos listas distintas darian catalogos
#: distintos segun cuando nacio la empresa, y la diferencia recien se veria
#: comparando dos cuentas.
#:
#: Los codigos de severidad son los tres del CHECK vigente de
#: `nonconformities.severity`: el catalogo se monta encima, no lo reemplaza.
SEVERIDADES_POR_DEFECTO: list[tuple[str, str, int]] = [
    ("minor", "Menor", 1),
    ("major", "Mayor", 2),
    ("critical", "Crítica", 3),
]

#: Las dos herramientas que la norma y la entrevista nombran, mas el analisis
#: que no sigue ninguna de las dos. No son invencion nuestra.
METODOLOGIAS_POR_DEFECTO: list[tuple[str, str, str]] = [
    ("cinco_porques", "5 ¿Por qué?", "cinco_porques"),
    ("ishikawa", "Diagrama de Ishikawa (causa-efecto)", "espina_pescado"),
    ("descriptivo", "Análisis descriptivo", "texto_libre"),
]


class ErrorDeCatalogo(ValueError):
    """Algo que el catalogo de esta empresa no admite."""


class SeveridadNoDisponible(ErrorDeCatalogo):
    """El nivel no esta en el catalogo de la empresa, o esta desactivado."""


class SinNivelesDeSeveridad(ErrorDeCatalogo):
    """La empresa se quedo sin ningun nivel activo.

    Se distingue de `SeveridadNoDisponible` porque el arreglo es otro: aca no
    hay ningun valor que sirva, y quien registre un hallazgo no tiene forma de
    adivinarlo. Es el mismo error que dejaba un pipeline de CRM sin etapas
    abiertas — una configuracion que no falla, deja el modulo inservible.
    """


def sembrar_por_defecto(db: Session, tenant_id: UUID) -> int:
    """Deja a una empresa con sus catalogos. Idempotente por codigo.

    **Hace falta porque el `CROSS JOIN tenants` de la migracion corre una sola
    vez**, al aplicarla: siembra a las empresas que existian ese dia y ninguna
    creada despues recibe nada. Es exactamente lo que paso con las etapas del
    CRM, y ahi el sintoma no se veia como un error — el kanban sin columnas se
    lee como una empresa que todavia no vende.

    Idempotente tambien porque sirve para reparar una empresa que quedo a
    medias, no solo para dar de alta una nueva.
    """
    creados = 0

    existentes = set(
        db.scalars(
            select(ImprovementSeverity.code).where(
                ImprovementSeverity.tenant_id == tenant_id,
                ImprovementSeverity.deleted_at.is_(None),
            )
        ).all()
    )
    for code, label, rank in SEVERIDADES_POR_DEFECTO:
        if code in existentes:
            continue
        db.add(
            ImprovementSeverity(
                tenant_id=tenant_id, code=code, label=label, rank=rank
            )
        )
        creados += 1

    existentes = set(
        db.scalars(
            select(ImprovementMethodology.code).where(
                ImprovementMethodology.tenant_id == tenant_id,
                ImprovementMethodology.deleted_at.is_(None),
            )
        ).all()
    )
    for code, name, shape in METODOLOGIAS_POR_DEFECTO:
        if code in existentes:
            continue
        db.add(
            ImprovementMethodology(
                tenant_id=tenant_id, code=code, name=name, shape=shape
            )
        )
        creados += 1

    db.flush()
    return creados


def niveles_activos(db: Session, tenant_id: UUID) -> list[ImprovementSeverity]:
    """Los niveles que la empresa puede usar hoy, de mas leve a mas grave."""
    return list(
        db.scalars(
            select(ImprovementSeverity)
            .where(
                ImprovementSeverity.tenant_id == tenant_id,
                ImprovementSeverity.active.is_(True),
                ImprovementSeverity.deleted_at.is_(None),
            )
            .order_by(ImprovementSeverity.rank)
        ).all()
    )


def comprobar_severidad(
    db: Session, tenant_id: UUID, code: str
) -> ImprovementSeverity:
    """El nivel, si esta activo en el catalogo de la empresa. Si no, explica cual.

    Devuelve la fila y no `None`/`True` porque quien llama necesita el plazo,
    y volver a buscarla seria dos consultas para una pregunta.
    """
    activos = niveles_activos(db, tenant_id)

    if not activos:
        raise SinNivelesDeSeveridad(
            "Esta empresa no tiene ningun nivel de severidad activo, asi que no "
            "se puede registrar un hallazgo. Se configuran en el catalogo de "
            "severidades."
        )

    for nivel in activos:
        if nivel.code == code:
            return nivel

    disponibles = ", ".join(n.code for n in activos)
    raise SeveridadNoDisponible(
        f"La severidad '{code}' no esta activa en el catalogo de esta empresa. "
        f"Disponibles: {disponibles}."
    )


def fecha_limite(nivel: ImprovementSeverity, desde: date) -> date | None:
    """Cuando hay que cerrar un hallazgo de este nivel.

    **`None` cuando la empresa no declaro plazo**, que es el estado inicial de
    todas. Devolver una fecha ahi seria inventar un compromiso que nadie tomo, y
    quien la viera en pantalla la leeria como acordada.
    """
    if nivel.days_to_close is None:
        return None
    return desde + timedelta(days=nivel.days_to_close)
