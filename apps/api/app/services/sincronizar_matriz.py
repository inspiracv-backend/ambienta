"""Llevar la normativa aplicable a la matriz de la empresa (RF-19, RF-29).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

Es el paso que convierte "estas normas te corresponden" en filas que alguien
puede evaluar. Va aparte del calculo a proposito: el negocio pidio **un check**
de normativas recomendadas, y un check es una revision humana antes de
comprometer. Generar la matriz de golpe le daria a la empresa cientos de
articulos sin que nadie mirara si tienen sentido.

## La regla que gobierna todo: se sincroniza, no se reemplaza

Correrlo dos veces no duplica ni pisa. En concreto:

- **Agrega** lo que falta.
- **Nunca borra.** Lo que dejo de corresponder se marca `not_applicable` con su
  motivo. Borrarlo eliminaria la evidencia de que en su momento se evaluo, que
  es lo que pide un fiscalizador al revisar un periodo pasado.
- **Respeta lo agregado a mano.** Que el calculo no encuentre una norma no
  significa que no aplique: puede venir de un contrato o de la RCA de la
  empresa. Un recalculo no la quita.
- **Conserva las evaluaciones.** Una fila ya evaluada no vuelve a "pendiente".

## Los articulos entran sin evaluar, no incumplidos

`compliance_status = 'pending'`. No haber evaluado no es incumplir, y contarlo
como incumplimiento hundiria el porcentaje de la empresa el dia que se le carga
la matriz.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.catalog import LegalArticle, LegalNorm, LegalNormVersion
from ..models.compliance import ArticleCompliance, MatrixNorm, TenantLegalMatrix
from .normativa_aplicable import calcular

#: Motivo que se escribe al marcar una norma que dejo de corresponder.
MOTIVO_YA_NO_APLICA = (
    "El calculo por sector dejo de incluirla. Se conserva para no perder las "
    "evaluaciones hechas mientras aplicaba."
)


@dataclass(frozen=True)
class ResultadoSincronizacion:
    """Que cambio, para poder decirselo a quien lo pidio."""

    normas_agregadas: int = 0
    normas_ya_estaban: int = 0
    normas_marcadas_no_aplicables: int = 0
    articulos_agregados: int = 0
    evaluaciones_conservadas: int = 0
    #: Si el calculo no pudo correr, por que. `None` cuando si corrio.
    sin_calcular: str | None = None


def _version_vigente(db: Session, norm_id: UUID) -> UUID | None:
    return db.scalar(
        select(LegalNormVersion.id).where(
            LegalNormVersion.norm_id == norm_id,
            LegalNormVersion.is_current.is_(True),
            LegalNormVersion.deleted_at.is_(None),
        )
    )


def sincronizar(
    db: Session, matrix_id: UUID, tenant_id: UUID, autor_id: UUID | None = None
) -> ResultadoSincronizacion:
    """Deja la matriz alineada con la normativa que hoy le corresponde.

    No hace `commit`: lo decide quien llama, para que la operacion entera sea
    una sola transaccion. Consultar despues de un `commit` ademas veria cero
    filas —el tenant declarado se va con la transaccion— y este servicio lee
    despues de escribir.
    """
    matriz = db.get(TenantLegalMatrix, matrix_id)
    if matriz is None:
        raise ValueError("Matrix not found")

    aplicable = calcular(db, tenant_id)
    if aplicable.estado != "con_normativa":
        # No se toca nada. Un sector sin clasificar no significa que la empresa
        # no tenga obligaciones, asi que marcar como "ya no aplican" las que ya
        # estan seria justo la conclusion equivocada.
        return ResultadoSincronizacion(sin_calcular=aplicable.estado)

    corresponden = {
        n.norm_id: n for n in (*aplicable.obligatorias, *aplicable.recomendadas)
    }

    existentes = {
        mn.norm_id: mn
        for mn in db.scalars(
            select(MatrixNorm).where(
                MatrixNorm.matrix_id == matrix_id,
                MatrixNorm.deleted_at.is_(None),
            )
        )
    }

    agregadas = ya_estaban = marcadas = articulos = conservadas = 0

    for norm_id, propuesta in corresponden.items():
        fila = existentes.get(norm_id)
        if fila is None:
            vigente = _version_vigente(db, norm_id)
            if vigente is None:
                # Sin version vigente no hay articulado que evaluar. Se omite en
                # vez de crear una norma vacia que aparenta trabajo pendiente.
                continue
            fila = MatrixNorm(
                tenant_id=tenant_id,
                matrix_id=matrix_id,
                norm_id=norm_id,
                selected_version_id=vigente,
                sector_id=propuesta.sector_id,
                applicability="applicable",
                applicability_reason=propuesta.rationale,
                inclusion_source="automatic",
                created_by=autor_id,
            )
            db.add(fila)
            db.flush()
            agregadas += 1
            articulos += _sembrar_articulos(db, fila, tenant_id)
        else:
            ya_estaban += 1
            # Vuelve a aplicar: si estaba marcada como no aplicable, se
            # reactiva. Sus evaluaciones siguen donde estaban.
            if fila.applicability == "not_applicable":
                fila.applicability = "applicable"
                fila.applicability_reason = propuesta.rationale
            articulos += _sembrar_articulos(db, fila, tenant_id)

    for norm_id, fila in existentes.items():
        if norm_id in corresponden:
            continue
        if fila.inclusion_source == "manual":
            # Que el calculo no la encuentre no significa que no aplique.
            continue
        if fila.applicability != "not_applicable":
            fila.applicability = "not_applicable"
            fila.applicability_reason = MOTIVO_YA_NO_APLICA
            marcadas += 1

    # Cuantas evaluaciones sobrevivieron. Es el numero que hace verificable la
    # promesa de "no pisa lo evaluado": si baja tras sincronizar, algo borro.
    conservadas = db.scalar(
        select(func.count())
        .select_from(ArticleCompliance)
        .where(
            ArticleCompliance.tenant_id == tenant_id,
            ArticleCompliance.compliance_status != "pending",
        )
    )

    return ResultadoSincronizacion(
        normas_agregadas=agregadas,
        normas_ya_estaban=ya_estaban,
        normas_marcadas_no_aplicables=marcadas,
        articulos_agregados=articulos,
        evaluaciones_conservadas=conservadas,
    )


def _sembrar_articulos(db: Session, fila: MatrixNorm, tenant_id: UUID) -> int:
    """Crea la evaluacion pendiente de cada articulo que todavia no la tenga.

    Se consulta cuales existen en vez de insertar con `ON CONFLICT`: la
    unicidad es `(matrix_norm_id, article_id, facility_id)` con NULLS NOT
    DISTINCT, y apoyarse en el conflicto haria que un error de datos —dos
    articulos con el mismo id— pasara como "ya estaba".
    """
    articulos = db.scalars(
        select(LegalArticle.id).where(
            LegalArticle.norm_version_id == fila.selected_version_id,
            LegalArticle.deleted_at.is_(None),
        )
    ).all()
    if not articulos:
        return 0

    ya_estan = set(
        db.scalars(
            select(ArticleCompliance.article_id).where(
                ArticleCompliance.matrix_norm_id == fila.id
            )
        ).all()
    )

    creados = 0
    for article_id in articulos:
        if article_id in ya_estan:
            continue
        db.add(
            ArticleCompliance(
                tenant_id=tenant_id,
                matrix_norm_id=fila.id,
                article_id=article_id,
                # Sin evaluar, no incumplido: no haber evaluado no es incumplir.
                compliance_status="pending",
            )
        )
        creados += 1
    return creados


@dataclass(frozen=True)
class NormaDesactualizada:
    """Una norma de la matriz que se evaluo contra una version que ya no rige."""

    matrix_norm_id: UUID
    norm_id: UUID
    title: str
    version_evaluada: UUID
    version_vigente: UUID
    #: Cuantas evaluaciones se hicieron sobre la version anterior. **No se
    #: invalidan**: se hicieron sobre el texto que regia entonces, y esa es la
    #: respuesta correcta ante una auditoria de ese periodo.
    evaluaciones_sobre_la_anterior: int


def desactualizadas(db: Session, matrix_id: UUID) -> list[NormaDesactualizada]:
    """Que normas de la matriz quedaron con una version vieja.

    ## Por que compara versiones y no fechas

    Una norma puede tener correcciones que no cambian el articulado. El esquema
    ya distingue versiones con `content_hash`, asi que comparar
    `selected_version_id` contra la que tiene `is_current` da la respuesta
    exacta; comparar fechas reintroduciria falsos positivos que el versionado ya
    evita.

    ## Lo que esto NO hace

    No migra las evaluaciones ni las invalida. Avisa. Pasar una evaluacion de
    una version a otra es otro problema —los articulos pueden haberse
    renumerado, partido o desaparecido— y merece su propio cambio.
    """
    filas = db.execute(
        select(
            MatrixNorm.id,
            MatrixNorm.norm_id,
            MatrixNorm.selected_version_id,
            LegalNormVersion.id,
        )
        .join(
            LegalNormVersion,
            (LegalNormVersion.norm_id == MatrixNorm.norm_id)
            & LegalNormVersion.is_current.is_(True)
            & LegalNormVersion.deleted_at.is_(None),
        )
        .where(
            MatrixNorm.matrix_id == matrix_id,
            MatrixNorm.deleted_at.is_(None),
            # Una norma que ya no aplica no necesita aviso de version: no se
            # esta evaluando contra ninguna.
            MatrixNorm.applicability != "not_applicable",
            MatrixNorm.selected_version_id != LegalNormVersion.id,
        )
    ).all()

    if not filas:
        return []

    titulos = dict(
        db.execute(
            select(LegalNorm.id, LegalNorm.title).where(
                LegalNorm.id.in_([f[1] for f in filas])
            )
        ).all()
    )

    resultado = []
    for mn_id, norm_id, evaluada, vigente in filas:
        hechas = db.scalar(
            select(func.count())
            .select_from(ArticleCompliance)
            .where(
                ArticleCompliance.matrix_norm_id == mn_id,
                ArticleCompliance.compliance_status != "pending",
            )
        )
        resultado.append(
            NormaDesactualizada(
                matrix_norm_id=mn_id,
                norm_id=norm_id,
                title=titulos.get(norm_id, ""),
                version_evaluada=evaluada,
                version_vigente=vigente,
                evaluaciones_sobre_la_anterior=hechas or 0,
            )
        )
    return resultado
