"""Lo que la empresa esta incumpliendo ahora mismo (#126, epica #23).

La vista de detalle del tablero ejecutivo: el numero grande dice *cuanto*, esto
dice *que*. Sin ella, un "3 incumplimientos" en el dashboard obliga a abrir
norma por norma para descubrir cuales.

## Dos cosas distintas, y por eso van juntas

Un incumplimiento puede ser de dos naturalezas y se atienden distinto:

- **Un articulo evaluado como `non_compliant`** — un requisito legal que la
  empresa reconoce que no cumple. Se resuelve con un plan de accion.
- **Una declaracion vencida** — un tramite que no se presento a tiempo. Se
  resuelve presentandolo, y cada dia que pasa cuenta.

Mezclarlos en una sola lista sin distinguirlos haria que la urgencia de una
tapara la de la otra. Van en la misma respuesta pero en colecciones separadas.

## La evidencia es el eje, y por eso se separa lo que no la tiene

Un incumplimiento **con** evidencia es uno documentado: hay un informe, una
medicion, algo que mostrar sobre por que no se cumple y que se esta haciendo.
Uno **sin** evidencia es el que deja a la empresa sin nada que decir cuando
llega la fiscalizacion.

Los dos son incumplimientos, pero el segundo es el que hay que atender primero,
asi que la respuesta trae el conteo aparte en vez de obligar a la pantalla a
recorrer la lista para saberlo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.catalog import LegalArticle, LegalNorm
from ..models.compliance import ArticleCompliance, MatrixNorm, TenantLegalMatrix
from ..models.organization import Facility
from ..models.obligations import Obligation

#: Cuantas filas devuelve como maximo cada coleccion.
#:
#: Hay tope **y la respuesta dice si se corto**. Una lista truncada en silencio
#: se lee como "esto es todo lo que hay", que sobre incumplimientos es
#: exactamente la lectura que no puede darse.
TOPE = 200


def _articulos(db: Session, tenant_id: UUID) -> list[dict]:
    filas = db.execute(
        select(
            ArticleCompliance.id,
            LegalNorm.title,
            LegalNorm.norm_number,
            LegalArticle.article_number,
            LegalArticle.heading,
            Facility.name,
            ArticleCompliance.evidence_url,
            ArticleCompliance.compliance_method,
            ArticleCompliance.responsible_user_id,
            ArticleCompliance.assessed_at,
            ArticleCompliance.risk_level,
        )
        .select_from(ArticleCompliance)
        .join(MatrixNorm, MatrixNorm.id == ArticleCompliance.matrix_norm_id)
        .join(TenantLegalMatrix, TenantLegalMatrix.id == MatrixNorm.matrix_id)
        .join(LegalNorm, LegalNorm.id == MatrixNorm.norm_id)
        .join(LegalArticle, LegalArticle.id == ArticleCompliance.article_id)
        # `outerjoin`: `facility_id` es nullable — un articulo evaluado a nivel
        # de empresa no cuelga de ninguna planta, y con un join normal esos
        # incumplimientos **desaparecerian de la lista sin dejar rastro**.
        .outerjoin(Facility, Facility.id == ArticleCompliance.facility_id)
        .where(
            TenantLegalMatrix.tenant_id == tenant_id,
            ArticleCompliance.compliance_status == "non_compliant",
            ArticleCompliance.deleted_at.is_(None),
            MatrixNorm.deleted_at.is_(None),
            TenantLegalMatrix.deleted_at.is_(None),
        )
        # Sin evidencia primero: es lo que hay que atender antes.
        .order_by(
            ArticleCompliance.evidence_url.is_(None).desc(),
            LegalNorm.norm_number,
            LegalArticle.display_order,
        )
        .limit(TOPE + 1)
    ).all()

    return [
        {
            "article_compliance_id": f[0],
            "norm_title": f[1],
            "norm_number": f[2],
            "article_number": f[3],
            "article_heading": f[4],
            "facility_name": f[5],
            "evidence_url": f[6],
            "compliance_method": f[7],
            "responsible_user_id": f[8],
            "assessed_at": f[9],
            "risk_level": f[10],
        }
        for f in filas
    ]


def _declaraciones(db: Session, tenant_id: UUID, ahora: datetime) -> list[dict]:
    """Las declaraciones vencidas y todavia sin resolver.

    El vencimiento se mide por fecha **y** por estado, no por el estado a secas:
    `status = 'overdue'` solo existe si alguien o algo lo escribio, y hoy nada
    lo hace automaticamente. Una declaracion abierta con la fecha pasada esta
    vencida aunque su columna diga `open`.
    """
    filas = db.execute(
        select(
            Obligation.id,
            Obligation.code,
            Obligation.title,
            Obligation.due_at,
            Obligation.status,
            Obligation.external_receipt,
            Obligation.owner_user_id,
            Facility.name,
        )
        .select_from(Obligation)
        .outerjoin(Facility, Facility.id == Obligation.facility_id)
        .where(
            Obligation.tenant_id == tenant_id,
            Obligation.deleted_at.is_(None),
            Obligation.due_at.is_not(None),
            Obligation.due_at < ahora,
            # Aceptada o cerrada no es incumplimiento, aunque la fecha ya paso.
            Obligation.status.not_in(["accepted", "closed"]),
        )
        .order_by(Obligation.due_at)
        .limit(TOPE + 1)
    ).all()

    return [
        {
            "obligation_id": f[0],
            "code": f[1],
            "title": f[2],
            "due_at": f[3],
            "status": f[4],
            "external_receipt": f[5],
            "owner_user_id": f[6],
            "facility_name": f[7],
            "days_overdue": (ahora - f[3]).days if f[3] else None,
        }
        for f in filas
    ]


def listar(db: Session, tenant_id: UUID, ahora: datetime | None = None) -> dict:
    """Todo lo que esta en incumplimiento, con su evidencia si la hay."""
    ahora = ahora or datetime.now(timezone.utc)

    articulos = _articulos(db, tenant_id)
    declaraciones = _declaraciones(db, tenant_id, ahora)

    return {
        "generated_at": ahora,
        "articles": articulos[:TOPE],
        "declarations": declaraciones[:TOPE],
        # **Se dice cuando se corto.** Ver `TOPE`.
        "articles_truncated": len(articulos) > TOPE,
        "declarations_truncated": len(declaraciones) > TOPE,
        "articles_without_evidence": sum(
            1 for a in articulos[:TOPE] if not a["evidence_url"]
        ),
    }
