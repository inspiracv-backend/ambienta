"""Significancia de un aspecto ambiental — ISO 14001 §6.1.2 (#44).

## Que estaba escrito aca antes, y por que no podia funcionar

La version anterior tenia cuatro defectos en treinta lineas, y **ninguno era
visible porque nada la llamaba** — el mismo patron de `bcn.sincronizar()` y
`control_documental.py`:

| Defecto | Realidad |
|---|---|
| Leia `aspect.detection_score` | Esa columna **no existe**: da `AttributeError` |
| Validaba los puntajes en `1..5` | La base admite `1..10`: media escala inalcanzable |
| Escribia `significance = 'significant'` | El CHECK no lo admitia hasta `db/21` |
| Nunca escribia `total_score` | La columna existe justo para eso |

## Los criterios son un defecto razonable, no una verdad

ISO 14001 **no fija** como se calcula la significancia: dice que la
organizacion establezca sus propios criterios y los aplique de forma
consistente. Asi que los numeros de aca son un punto de partida defendible, no
una regla del estandar, y #41 los va a mover a configuracion por empresa.

Mientras tanto se equivocan **hacia el lado seguro**: un aspecto marcado
significativo de mas cuesta trabajo; uno marcado de menos queda sin controles y
aparece en una auditoria.

## Sin puntajes no hay juicio, y eso NO es "no significativo"

La version anterior hacia `(aspect.frequency_score or 0)`. Un aspecto que nadie
evaluo daba total 0 y quedaba **`not_significant`**: el sistema afirmando que
un aspecto no importa cuando lo que pasa es que nadie lo miro. Es el mismo error
del `0 %` en las plantas sin evaluar del tablero, y en este modulo es peor
—significa que no se le ponen controles.

Sin los tres puntajes, la significancia queda en `pending` y se dice.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from ..models.iso14001 import EnvironmentalAspect

#: Los tres criterios, cada uno de 1 a 10 (lo que admite el CHECK de la tabla).
PUNTAJE_MINIMO = 1
PUNTAJE_MAXIMO = 10

#: `frecuencia x severidad` a partir del cual el aspecto se gestiona. 25 es
#: "ambos criterios alrededor de 5", o sea la mitad de la escala en los dos.
UMBRAL_DE_SIGNIFICANCIA = 25

#: Un requisito legal aplicable vuelve el aspecto significativo **por si solo**,
#: sin mirar la magnitud. Es practica corriente en 14001 y es la regla
#: conservadora: si hay una obligacion legal, el aspecto se gestiona aunque
#: ocurra poco y contamine poco — porque el incumplimiento no depende de eso.
LEGAL_QUE_OBLIGA = 8


class ErrorDeSignificancia(Exception):
    """No se puede juzgar la significancia con lo que hay."""


class PuntajeFueraDeRango(ErrorDeSignificancia):
    """Un criterio quedo fuera de 1..10."""


def _valida(nombre: str, valor: int) -> None:
    if not (PUNTAJE_MINIMO <= valor <= PUNTAJE_MAXIMO):
        raise PuntajeFueraDeRango(
            f"{nombre} tiene que estar entre {PUNTAJE_MINIMO} y {PUNTAJE_MAXIMO}; "
            f"llego {valor}."
        )


def calcular_significancia(
    frecuencia: int | None, severidad: int | None, legal: int | None
) -> tuple[int | None, str, list[str]]:
    """Devuelve `(total, significancia, motivos)`.

    Los **motivos** no son decoracion: en una auditoria la pregunta no es si el
    aspecto es significativo sino **por que**, y sin esto la respuesta seria un
    numero sin explicacion. Ademas hacen legible el caso raro pero correcto de
    un aspecto de magnitud baja que igual se gestiona porque hay una obligacion
    legal — que leyendo solo `total_score` pareceria un error.
    """
    if frecuencia is None or severidad is None or legal is None:
        return None, "pending", [
            "Faltan puntajes por asignar, asi que la significancia esta sin juzgar."
        ]

    for nombre, valor in (
        ("frequency_score", frecuencia),
        ("severity_score", severidad),
        ("legal_score", legal),
    ):
        _valida(nombre, valor)

    total = frecuencia * severidad
    motivos: list[str] = []

    if total >= UMBRAL_DE_SIGNIFICANCIA:
        motivos.append(
            f"Frecuencia x severidad = {total}, que alcanza el umbral de "
            f"{UMBRAL_DE_SIGNIFICANCIA}."
        )
    if legal >= LEGAL_QUE_OBLIGA:
        motivos.append(
            f"Hay un requisito legal aplicable (nivel {legal}), y eso lo vuelve "
            "significativo aunque la magnitud sea baja."
        )

    if motivos:
        return total, "significant", motivos

    return total, "not_significant", [
        f"Frecuencia x severidad = {total}, por debajo del umbral de "
        f"{UMBRAL_DE_SIGNIFICANCIA}, y sin requisito legal que obligue."
    ]


def evaluar_aspecto(
    db: Session,
    aspecto: EnvironmentalAspect,
    frecuencia: int,
    severidad: int,
    legal: int,
) -> list[str]:
    """Aplica los criterios y **guarda tambien el total**.

    `total_score` se escribe porque es lo que permite revisar el juicio despues
    sin recalcularlo: quien audita compara el numero con el umbral vigente. Sin
    guardarlo, cambiar el umbral reescribiria la historia en silencio.
    """
    total, significancia, motivos = calcular_significancia(frecuencia, severidad, legal)

    aspecto.frequency_score = frecuencia
    aspecto.severity_score = severidad
    aspecto.legal_score = legal
    aspecto.total_score = total
    aspecto.significance = significancia

    db.flush()
    return motivos


def aspectos_significativos(
    db: Session, tenant_id: UUID
) -> list[EnvironmentalAspect]:
    """Los que hay que gestionar. Es la entrada de §6.1.4 (#49)."""
    return list(
        db.scalars(
            select(EnvironmentalAspect).where(
                and_(
                    EnvironmentalAspect.tenant_id == tenant_id,
                    EnvironmentalAspect.significance == "significant",
                    EnvironmentalAspect.deleted_at.is_(None),
                )
            )
        ).all()
    )


def significativos_sin_riesgo(
    db: Session, tenant_id: UUID
) -> list[EnvironmentalAspect]:
    """Aspectos significativos que **nadie enlazo a un riesgo u oportunidad**.

    Es el hallazgo mas comun de una auditoria de 14001: la empresa identifico el
    aspecto, lo declaro significativo, y ahi se detuvo. §6.1.4 pide que de los
    aspectos significativos salgan riesgos y oportunidades con su tratamiento.

    Se calcula en el servidor y no en la pantalla porque el mismo dato lo va a
    querer un reporte, y dos implementaciones del mismo criterio se
    desincronizan solas.
    """
    from ..models.iso14001 import RiskOpportunity

    con_riesgo = select(RiskOpportunity.environmental_aspect_id).where(
        RiskOpportunity.tenant_id == tenant_id,
        RiskOpportunity.environmental_aspect_id.is_not(None),
        RiskOpportunity.deleted_at.is_(None),
    )
    return list(
        db.scalars(
            select(EnvironmentalAspect)
            .where(
                EnvironmentalAspect.tenant_id == tenant_id,
                EnvironmentalAspect.significance == "significant",
                EnvironmentalAspect.deleted_at.is_(None),
                EnvironmentalAspect.id.not_in(con_riesgo),
            )
            .order_by(EnvironmentalAspect.total_score.desc().nullslast())
        ).all()
    )
