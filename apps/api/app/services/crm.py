"""Las reglas del pipeline comercial (epica #32).

## Por que hay un servicio y no solo CRUD

Mover un trato de columna **no es editar un campo**. Segun a donde vaya:

- a una etapa `won` o `lost`, el trato **se cierra** — `closed_at` deja escrito
  cuando, que es lo que permite medir cuanto tarda un ciclo de venta;
- a `lost`, ademas **exige motivo**;
- de vuelta a una etapa `open`, el trato **se reabre** y hay que limpiar el
  cierre, o quedaria un trato activo con fecha de cierre y las metricas lo
  contarian dos veces.

Todo eso en un `PATCH` generico de `stage_id` se pierde: la pantalla movería la
tarjeta y el sistema no sabria que paso.

## Lo que la base impone y este servicio se adelanta a explicar

`ck_crm_activities_un_solo_padre` y `ck_crm_deals_perdido_con_motivo` viven en
Postgres, que es donde tienen que estar: un `UPDATE` a mano tambien tiene que
respetarlos. Aca se comprueban **antes** para responder un 422 legible en vez de
un error de restriccion, que se lee como un fallo del sistema y no como un dato
que falta.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.crm import CrmActivity, CrmCompany, CrmContact, CrmDeal, CrmStage

#: Cuantos tratos se traen por columna. El kanban se mira, no se recorre: una
#: columna con doscientas tarjetas no se lee, y traerlas todas hace lenta la
#: pantalla para nadie. Lo que se corta **se dice** (`truncado`).
TOPE_POR_COLUMNA = 50


class ErrorDeCrm(Exception):
    """La operacion pedida no corresponde."""


class SinEtapas(ErrorDeCrm):
    """La empresa no tiene ninguna etapa activa: no hay pipeline que dibujar."""


class MotivoRequerido(ErrorDeCrm):
    """Perder un trato exige decir por que."""


class PadreInvalido(ErrorDeCrm):
    """Una actividad cuelga de exactamente uno."""


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def etapas_de(db: Session, tenant_id: UUID) -> list[CrmStage]:
    """Las etapas activas, en su orden. Es el eje del kanban."""
    return list(
        db.scalars(
            select(CrmStage)
            .where(
                CrmStage.tenant_id == tenant_id,
                CrmStage.active.is_(True),
                CrmStage.deleted_at.is_(None),
            )
            .order_by(CrmStage.position, CrmStage.name)
        ).all()
    )


def primera_etapa(db: Session, tenant_id: UUID) -> CrmStage:
    """Donde entra un trato nuevo cuando nadie eligio columna.

    Se prefiere la primera **abierta** y no la primera a secas: si alguien
    reordena y deja "Perdido" arriba, un trato nuevo nacería perdido.
    """
    etapas = etapas_de(db, tenant_id)
    if not etapas:
        raise SinEtapas(
            "Esta empresa no tiene etapas de pipeline activas. Crea al menos una "
            "para poder registrar oportunidades."
        )
    abiertas = [e for e in etapas if e.kind == "open"]
    return (abiertas or etapas)[0]


def crear_deal(
    db: Session, tenant_id: UUID, datos: dict, stage_id: UUID | None = None
) -> CrmDeal:
    """Crea el trato, poniendolo en la primera etapa abierta si no se dijo cual."""
    etapa_id = stage_id or primera_etapa(db, tenant_id).id
    deal = CrmDeal(tenant_id=tenant_id, stage_id=etapa_id, **datos)
    db.add(deal)
    db.flush()
    return deal


def mover_de_etapa(
    db: Session, deal: CrmDeal, etapa: CrmStage, motivo: str | None = None
) -> list[str]:
    """Mueve el trato y devuelve **que mas paso** ademas del cambio de columna.

    Se devuelve la lista de efectos y no un booleano porque la pantalla tiene
    que poder decirlos: arrastrar una tarjeta a "Perdido" cierra el trato, y si
    eso ocurre en silencio la persona lo descubre cuando el trato ya no aparece
    en sus pendientes.
    """
    efectos: list[str] = []

    if etapa.kind == "lost":
        limpio = (motivo or "").strip()
        if not limpio:
            raise MotivoRequerido(
                "Perder un trato exige decir por que. La razon de tener un "
                "pipeline es aprender por que se pierde."
            )
        deal.lost_reason = limpio
        efectos.append(f"Se anoto el motivo: {limpio}")

    era_abierto = deal.closed_at is None

    if etapa.kind in ("won", "lost"):
        if era_abierto:
            deal.closed_at = _ahora()
            efectos.append("El trato quedo cerrado")
    else:
        if not era_abierto:
            # Reabrir tiene que limpiar el cierre. Si no, queda un trato activo
            # con fecha de cierre y las metricas lo cuentan de los dos lados.
            deal.closed_at = None
            deal.lost_reason = None
            efectos.append("El trato se reabrio y se limpio su cierre anterior")

    deal.stage_id = etapa.id
    db.flush()
    return efectos


def validar_padre_de_actividad(datos: dict) -> None:
    """Exactamente uno de los tres.

    Ninguno seria una actividad huerfana que no aparece en ninguna ficha; dos,
    la misma llamada contada dos veces en la linea de tiempo. La base lo impide
    igual; esto solo hace que el mensaje sea legible.
    """
    padres = [
        datos.get("crm_company_id"),
        datos.get("crm_contact_id"),
        datos.get("crm_deal_id"),
    ]
    cuantos = sum(1 for p in padres if p is not None)
    if cuantos == 0:
        raise PadreInvalido(
            "Una actividad tiene que colgar de una empresa, un contacto o una "
            "oportunidad. Sin eso no aparece en ninguna ficha."
        )
    if cuantos > 1:
        raise PadreInvalido(
            "Una actividad cuelga de una sola cosa. Con dos, la misma llamada "
            "sale duplicada en la linea de tiempo."
        )


def pipeline(db: Session, tenant_id: UUID) -> dict:
    """El kanban entero: columnas, tarjetas y totales.

    Dos cosas que este calculo hace a proposito y conviene no "simplificar":

    **1. Los totales se calculan sobre todo lo que hay**, no sobre lo que se
    devuelve. Sumar solo las tarjetas visibles daria un monto menor que el real
    en cuanto una columna pase del tope, y ese numero se cita despues en una
    reunion como si fuera el pipeline completo.

    **2. Se suma por moneda, no todo junto.** `currency` es un campo por trato
    y ningun CHECK lo fija en una sola: una columna con un trato de 1.000 CLP y
    otro de 1.000 USD sumados a secas da `2000`, que no es plata de ninguna
    clase. Un total mal sumado es peor que ninguno — el numero se ve razonable
    y nadie lo vuelve a mirar.
    """
    etapas = etapas_de(db, tenant_id)
    columnas = []
    truncado = False

    # Conteos y sumas de una vez, no por columna: con seis etapas serian doce
    # consultas mas para un dato que cabe en una.
    cuantos: dict[UUID, int] = {}
    montos: dict[UUID, list[tuple[str, Decimal]]] = {}
    for stage_id, moneda, total, suma in db.execute(
        select(
            CrmDeal.stage_id,
            CrmDeal.currency,
            func.count(CrmDeal.id),
            func.sum(CrmDeal.amount),
        )
        .where(CrmDeal.tenant_id == tenant_id, CrmDeal.deleted_at.is_(None))
        .group_by(CrmDeal.stage_id, CrmDeal.currency)
        .order_by(CrmDeal.currency)
    ).all():
        cuantos[stage_id] = cuantos.get(stage_id, 0) + total
        # Una moneda sin un solo monto declarado no aparece: la columna diria
        # "USD 0" por un trato al que todavia no le pusieron cifra, y eso se lee
        # como un trato de cero pesos y no como uno sin valorar.
        if suma is not None:
            montos.setdefault(stage_id, []).append((moneda, suma))

    for etapa in etapas:
        tarjetas = list(
            db.scalars(
                select(CrmDeal)
                .where(
                    CrmDeal.tenant_id == tenant_id,
                    CrmDeal.stage_id == etapa.id,
                    CrmDeal.deleted_at.is_(None),
                )
                # Lo que vence antes, arriba. Un trato sin fecha va al final:
                # `NULLS LAST` importa — sin el, Postgres los pone primero y la
                # columna se encabeza con lo que menos urge.
                .order_by(CrmDeal.expected_close_date.asc().nullslast(), CrmDeal.created_at)
                .limit(TOPE_POR_COLUMNA)
            ).all()
        )
        total = cuantos.get(etapa.id, 0)
        if total > len(tarjetas):
            truncado = True
        columnas.append(
            {
                "stage": etapa,
                "deals": tarjetas,
                "total_deals": total,
                "montos": montos.get(etapa.id, []),
            }
        )

    return {"columnas": columnas, "truncado": truncado}


def linea_de_tiempo(db: Session, tenant_id: UUID, *, deal_id: UUID | None = None,
                    company_id: UUID | None = None, limite: int = 100) -> list[CrmActivity]:
    """Las actividades de un trato o de una empresa, de lo mas nuevo a lo mas viejo.

    Para una empresa incluye **lo de sus tratos y sus contactos**, no solo lo
    colgado de la empresa: quien abre la ficha de un cliente quiere ver todo lo
    que paso con el, no la parte que alguien recordo anotar en el sitio
    correcto.
    """
    condiciones = [CrmActivity.tenant_id == tenant_id, CrmActivity.deleted_at.is_(None)]

    if deal_id is not None:
        condiciones.append(CrmActivity.crm_deal_id == deal_id)
    elif company_id is not None:
        deals = select(CrmDeal.id).where(CrmDeal.crm_company_id == company_id)
        contactos = select(CrmContact.id).where(CrmContact.crm_company_id == company_id)
        condiciones.append(
            (CrmActivity.crm_company_id == company_id)
            | CrmActivity.crm_deal_id.in_(deals)
            | CrmActivity.crm_contact_id.in_(contactos)
        )

    return list(
        db.scalars(
            select(CrmActivity)
            .where(*condiciones)
            .order_by(CrmActivity.occurred_at.desc())
            .limit(limite)
        ).all()
    )


class TratoNoGanado(ErrorDeCrm):
    """Solo un trato ganado se promueve a contrato."""


class YaPromovido(ErrorDeCrm):
    """El trato ya apunta a otro contrato."""


class ClienteDistinto(ErrorDeCrm):
    """El contrato es de otro cliente que el de la ficha."""


def promover_a_contrato(
    db: Session, deal: CrmDeal, contrato, etapa: CrmStage | None = None
) -> list[str]:
    """Enlaza el trato ganado con el contrato que lo materializo (#82).

    **No crea el contrato: lo enlaza.** Crearlo exige que el cliente ya sea un
    tenant de la plataforma, que es un alta con su propio flujo — y hacerlo aca
    de paso produciria empresas a medias creadas por arrastrar una tarjeta.

    Tres cosas que se niega a hacer, y por que cada una:

    **1. Promover un trato que no se gano.** Un contrato firmado colgando de un
    trato que sigue en negociacion —o que se perdio— no es un dato raro: es la
    lista de clientes contando a alguien que no lo es. `etapa` se pide para
    poder mirarlo; sin ella no se puede saber si el trato esta ganado, porque
    `closed_at` tambien lo pone una perdida.

    **2. Repuntar a otro contrato.** Si el trato ya apunta a uno, mover el
    enlace en silencio deja el contrato anterior huerfano y la trazabilidad de
    la venta rota. Repetir la promocion **con el mismo contrato** si se acepta:
    es la misma operacion otra vez, no una distinta.

    **3. Enlazar con el contrato de otro cliente.** `crm_companies.client_
    tenant_id` es el puente entre el prospecto y el tenant que ya existe. Si la
    ficha ya nombra a un tenant y el contrato nombra a otro, alguien se
    equivoco de contrato — y aceptarlo dejaria la ficha de una empresa apuntando
    a la relacion comercial de otra.
    """
    efectos: list[str] = []

    if etapa is not None and etapa.kind != "won":
        raise TratoNoGanado(
            "Solo un trato ganado se promueve a contrato. Este esta en "
            f"«{etapa.name}»: moverlo a una etapa de ganado primero."
        )

    if deal.contract_id is not None and deal.contract_id != contrato.id:
        raise YaPromovido(
            "Este trato ya esta enlazado a otro contrato. Mover el enlace "
            "dejaria el contrato anterior sin la venta que lo origino."
        )

    empresa = db.get(CrmCompany, deal.crm_company_id)
    if (
        empresa is not None
        and empresa.client_tenant_id is not None
        and empresa.client_tenant_id != contrato.client_tenant_id
    ):
        raise ClienteDistinto(
            "El contrato corresponde a otro cliente que el de esta ficha. "
            "Revisa cual es el contrato correcto."
        )

    ya_estaba = deal.contract_id == contrato.id
    deal.contract_id = contrato.id
    if not ya_estaba:
        efectos.append("El trato quedo enlazado al contrato")

    if empresa is not None:
        # El puente: la ficha comercial deja de ser un prospecto suelto y pasa
        # a nombrar al tenant que ya existe en la plataforma.
        if empresa.client_tenant_id is None:
            empresa.client_tenant_id = contrato.client_tenant_id
            efectos.append("La ficha quedo ligada al cliente en la plataforma")
        if empresa.status != "client":
            empresa.status = "client"
            efectos.append(f"{empresa.name} pasa de prospecto a cliente")

    db.flush()
    return efectos
