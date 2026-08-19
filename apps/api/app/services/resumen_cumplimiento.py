"""Resumen de cumplimiento por norma y por instalacion (#109).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

## Como se calcula el porcentaje, y por que asi

Es el numero que la empresa muestra ante un fiscalizador, asi que cada decision
sobre el denominador importa mas que la formula.

**Denominador**: los articulos que la empresa **debe cumplir**. Quedan fuera:

- Los **excluidos del calculo** (RF-24, `attributes.incluidoEnCalculo = false`).
  Sin esto la exclusion seria decorativa: se podria marcar y el numero no
  cambiaria.
- Los marcados **`not_applicable`**. Un articulo que no le aplica a la empresa
  no es una obligacion suya, y contarlo la penalizaria por algo que no le toca.

**Numerador**: solo `compliant`.

**`partial` cuenta como NO cumplido.** Dar por cumplido lo que la base dice que
se cumple a medias sobreestima el porcentaje ante un auditor, y la direccion
conservadora es la unica defendible. Es la misma decision que ya toma la
pantalla al leerlo.

**`pending` cuenta en el denominador.** No haber evaluado no es incumplir, pero
tampoco es cumplir: dejarlo fuera daria 100 % a una empresa que no evaluo nada.

## Dos porcentajes, no uno, y por que no se contradicen

La matriz en pantalla y este servicio calculaban lo mismo con denominadores
distintos: la pantalla dejaba lo pendiente **fuera** del denominador y mostraba
la cobertura al lado; aca entraba. Una empresa con un articulo cumplido y
diecinueve sin evaluar veia **100 %** en la matriz y **5 %** en el resumen.

Los dos numeros son correctos y responden preguntas distintas, asi que se
devuelven los dos desde el mismo conteo en vez de elegir uno:

- `porcentaje_sobre_evaluados` — de lo que se miro, cuanto se cumple
- `cobertura` — cuanto se alcanzo a mirar
- `porcentaje` — el conservador: lo pendiente cuenta como no cumplido

No son tres verdades sueltas. **El tercero es el producto de los otros dos**
—salvo una decima, porque cada uno se redondea por separado— asi que no pueden
contradecirse: si la pantalla muestra 100 % de cumplimiento sobre 5 % de
cobertura, el resumen dice 5 % y las tres cifras describen la misma realidad.

## Sin articulos que contar, el porcentaje es `None`

No es cero. Cero significa "no cumple nada"; `None` significa "todavia no hay
nada que medir". Mostrar 0 % a una empresa recien creada seria una acusacion
falsa, y es el mismo error que ya se corrigio distinguiendo "sector sin
clasificar" de "sin obligaciones".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.catalog import LegalNorm
from ..models.compliance import ArticleCompliance, MatrixNorm
from ..models.organization import Facility

#: Estados que no entran al denominador porque no son una obligacion pendiente.
FUERA_DEL_CALCULO = frozenset({"not_applicable"})


def cuenta_para_el_calculo(attributes: dict | None) -> bool:
    """Si este articulo entra al porcentaje.

    **Ausente significa incluido.** Tratar "no dice nada" como excluido sacaria
    del calculo a todos los articulos que nadie toco —o sea casi todos— y el
    porcentaje quedaria sobre un punado de filas. Es la misma regla que aplica
    el frontend, y esta escrita en los dos lados a proposito: el numero se
    calcula aca, y si difirieran la pantalla mostraria uno y el informe otro.
    """
    if not isinstance(attributes, dict):
        return True
    return attributes.get("incluidoEnCalculo") is not False


@dataclass
class Conteo:
    """Un grupo de articulos y como esta cada uno."""

    cumplen: int = 0
    no_cumplen: int = 0
    sin_evaluar: int = 0
    no_aplican: int = 0
    excluidos: int = 0

    @property
    def evaluables(self) -> int:
        """Los que la empresa debe cumplir: el denominador."""
        return self.cumplen + self.no_cumplen + self.sin_evaluar

    @property
    def evaluados(self) -> int:
        """Los que alguien ya miro: `sin_evaluar` no entra."""
        return self.cumplen + self.no_cumplen

    @property
    def porcentaje(self) -> float | None:
        """El numero conservador: lo pendiente cuenta como no cumplido.

        `None` cuando no hay nada que medir. **No es cero.**
        """
        if self.evaluables == 0:
            return None
        return round(self.cumplen / self.evaluables * 100, 1)

    @property
    def porcentaje_sobre_evaluados(self) -> float | None:
        """De lo que se evaluo, cuanto se cumple. **Es el que muestra la matriz.**

        Distinto de `porcentaje` en un solo punto: aca lo pendiente **no** entra
        al denominador. Una norma con un articulo en SI y quince sin evaluar da
        100 % — cierto sobre la muestra y enganoso sobre la norma.

        Por eso nunca va solo: se lee junto a `cobertura`, y el par responde dos
        preguntas distintas —"cuanto cumplimos" y "cuanto alcanzamos a
        revisar"— en vez de esconder una dentro de la otra.
        """
        if self.evaluados == 0:
            return None
        return round(self.cumplen / self.evaluados * 100, 1)

    @property
    def cobertura(self) -> float | None:
        """Cuanto se alcanzo a revisar de lo que la empresa debe cumplir.

        **Los excluidos del calculo no salen de aca.** Excluir un articulo del
        cumplimiento es una decision legitima; esconderlo de la cobertura seria
        tapar que nadie lo miro. Es la misma regla que ya aplica la matriz.
        """
        if self.evaluables == 0:
            return None
        return round(self.evaluados / self.evaluables * 100, 1)

    def sumar(self, estado: str, incluido: bool) -> None:
        if not incluido:
            self.excluidos += 1
        elif estado in FUERA_DEL_CALCULO:
            self.no_aplican += 1
        elif estado == "compliant":
            self.cumplen += 1
        elif estado == "pending":
            self.sin_evaluar += 1
        else:
            # `non_compliant` y `partial`. Cumplir a medias no es cumplir.
            self.no_cumplen += 1


@dataclass
class ResumenPorNorma:
    norm_id: UUID
    matrix_norm_id: UUID
    title: str
    applicability: str
    conteo: Conteo = field(default_factory=Conteo)


@dataclass
class ResumenPorInstalacion:
    #: `None` = evaluado a nivel empresa, sin planta concreta.
    facility_id: UUID | None
    nombre: str
    conteo: Conteo = field(default_factory=Conteo)


@dataclass
class ResumenDeMatriz:
    total: Conteo
    por_norma: list[ResumenPorNorma]
    por_instalacion: list[ResumenPorInstalacion]


def resumir(db: Session, matrix_id: UUID) -> ResumenDeMatriz:
    """Como va el cumplimiento de esta matriz, desglosado.

    Una sola consulta por matriz en vez de una por norma: con 30 normas de 200
    articulos, el bucle anidado hace 31 viajes a la base para responder algo que
    ya esta en una tabla.
    """
    filas = db.execute(
        select(
            MatrixNorm.id,
            MatrixNorm.norm_id,
            MatrixNorm.applicability,
            LegalNorm.title,
            ArticleCompliance.compliance_status,
            ArticleCompliance.facility_id,
            ArticleCompliance.attributes,
        )
        .join(LegalNorm, LegalNorm.id == MatrixNorm.norm_id)
        .outerjoin(
            ArticleCompliance,
            (ArticleCompliance.matrix_norm_id == MatrixNorm.id)
            & ArticleCompliance.deleted_at.is_(None),
        )
        .where(
            MatrixNorm.matrix_id == matrix_id,
            MatrixNorm.deleted_at.is_(None),
        )
    ).all()

    total = Conteo()
    normas: dict[UUID, ResumenPorNorma] = {}
    plantas: dict[UUID | None, ResumenPorInstalacion] = {}

    for mn_id, norm_id, aplicabilidad, titulo, estado, facility_id, attrs in filas:
        if mn_id not in normas:
            normas[mn_id] = ResumenPorNorma(
                norm_id=norm_id,
                matrix_norm_id=mn_id,
                title=titulo or "",
                applicability=aplicabilidad,
            )
        # El `outerjoin` deja una fila con estado nulo cuando la norma todavia
        # no tiene articulos sembrados. Aparece en el desglose con conteo en
        # cero —que es informacion: dice que esta en la matriz y sin evaluar—
        # pero no suma nada.
        if estado is None:
            continue

        incluido = cuenta_para_el_calculo(attrs)
        total.sumar(estado, incluido)
        normas[mn_id].conteo.sumar(estado, incluido)

        if facility_id not in plantas:
            plantas[facility_id] = ResumenPorInstalacion(
                facility_id=facility_id, nombre=""
            )
        plantas[facility_id].conteo.sumar(estado, incluido)

    _nombrar_instalaciones(db, plantas)

    return ResumenDeMatriz(
        total=total,
        por_norma=sorted(normas.values(), key=lambda n: n.title),
        por_instalacion=sorted(plantas.values(), key=lambda p: p.nombre),
    )


def _nombrar_instalaciones(
    db: Session, plantas: dict[UUID | None, ResumenPorInstalacion]
) -> None:
    """Le pone nombre a cada instalacion; el grupo sin planta se rotula aparte."""
    ids = [f for f in plantas if f is not None]
    nombres = (
        dict(
            db.execute(
                select(Facility.id, Facility.name).where(Facility.id.in_(ids))
            ).all()
        )
        if ids
        else {}
    )
    for fid, resumen in plantas.items():
        resumen.nombre = (
            "Toda la empresa" if fid is None else nombres.get(fid, "(instalacion desconocida)")
        )
