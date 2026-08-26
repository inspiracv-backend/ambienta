"""Contrato del Dashboard. De aca sale el OpenAPI que consume el frontend."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CriticalDeadline(BaseModel):
    """La obligacion pendiente mas proxima a vencer."""

    obligation_id: str
    code: str
    title: str
    due_at: str | None = None
    days_remaining: int | None = Field(
        default=None,
        description="Negativo si ya vencio. Null si la obligacion no tiene fecha.",
    )
    status: str


class GlobalMetrics(BaseModel):
    compliance_percentage: float | None = Field(
        description=(
            "0 a 100, un decimal. Los articulos 'not_applicable' salen del "
            "denominador; los 'not_evaluated' se quedan dentro, para que una "
            "matriz a medio evaluar no pueda mostrar 100%."
        ),
    )
    articles_evaluated: int = Field(
        description="Denominador del porcentaje: articulos que aplican."
    )
    articles_non_compliant: int
    total_obligations: int = Field(
        description="Obligaciones pendientes: todas salvo 'accepted' y 'closed'."
    )
    nc_open: int = Field(
        description="No conformidades activas: todas salvo 'closed' y 'rejected'."
    )
    obligations_upcoming: int = Field(
        description="Pendientes que vencen dentro de la ventana `days_ahead`."
    )
    obligations_overdue: int = Field(description="Pendientes con fecha ya pasada.")


class FacilityMetrics(BaseModel):
    facility_id: str
    name: str
    # El reporte de cumplimiento en PDF los imprime en la cabecera de cada
    # planta; sin ellos habria que pedir /facilities aparte solo para eso.
    commune_code: str | None = None
    region_code: str | None = None
    #: `None` = todavia no hay articulos evaluados. **No es cero:** cero
    #: significa que no se cumple nada, y son cosas distintas.
    compliance_percentage: float | None
    non_compliant_count: int
    nc_open_count: int
    critical_deadline: CriticalDeadline | None = None


class DashboardMetrics(BaseModel):
    tenant_id: str
    generated_at: str
    global_: GlobalMetrics = Field(
        alias="global",
        serialization_alias="global",
        description="`global` es palabra reservada en Python; se expone con alias.",
    )
    critical_deadline: CriticalDeadline | None = None
    upcoming_deadlines: list[CriticalDeadline] = Field(
        default_factory=list,
        description=(
            "Los 5 mas proximos, uno por planta. Alimentan la lista de S-06; "
            "salen de las mismas filas que el critico, sin consulta extra."
        ),
    )
    facilities: list[FacilityMetrics] = Field(
        description=(
            "Una fila por planta activa, incluidas las que no tienen nada "
            "cargado: una planta vacia es justamente la que conviene ver."
        ),
    )

    model_config = {"populate_by_name": True}


# ── Vista de incumplimientos (#126) ───────────────────────────────────────

class ArticuloEnIncumplimiento(BaseModel):
    """Un requisito legal que la empresa reconoce que no cumple."""

    article_compliance_id: UUID
    norm_title: str
    norm_number: str
    article_number: str
    article_heading: str | None
    #: `None` = evaluado a nivel de empresa, sin planta concreta.
    facility_name: str | None
    #: El enlace a la evidencia. **`None` es el caso que importa:** un
    #: incumplimiento sin nada que mostrar deja a la empresa muda ante una
    #: fiscalizacion.
    evidence_url: str | None
    compliance_method: str | None
    responsible_user_id: UUID | None
    assessed_at: datetime | None
    risk_level: str | None


class DeclaracionVencida(BaseModel):
    """Un tramite que no se presento a tiempo."""

    obligation_id: UUID
    code: str
    title: str
    due_at: datetime | None
    status: str
    external_receipt: str | None
    owner_user_id: UUID | None
    facility_name: str | None
    days_overdue: int | None


class Incumplimientos(BaseModel):
    """Lo que la empresa esta incumpliendo ahora mismo.

    Las dos colecciones van separadas a proposito: un articulo incumplido se
    resuelve con un plan de accion y una declaracion vencida se resuelve
    presentandola. Mezclarlas haria que la urgencia de una tapara la de la otra.
    """

    generated_at: datetime
    articles: list[ArticuloEnIncumplimiento]
    declarations: list[DeclaracionVencida]
    #: `true` = la lista se corto en el tope. **Se dice en vez de truncar en
    #: silencio:** una lista cortada sin avisar se lee como "esto es todo".
    articles_truncated: bool
    declarations_truncated: bool
    #: Cuantos de los articulos listados no tienen evidencia. Va aparte para que
    #: la pantalla no tenga que recorrer la lista para saberlo.
    articles_without_evidence: int
