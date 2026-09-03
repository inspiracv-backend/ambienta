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


class EtapaConTratos(ErrorDeCrm):
    """Retirar una columna que todavia tiene tarjetas las volveria invisibles."""


class UltimaEtapaDeSuTipo(ErrorDeCrm):
    """Sin una etapa activa de cada tipo, el pipeline deja de funcionar."""


class EtapaNoDisponible(ErrorDeCrm):
    """La columna destino no esta activa: el trato no se veria en el kanban."""


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


#: Las etapas con las que arranca una empresa. Son **las mismas** que siembra
#: `db/22_crm.sql`: dos listas distintas darian pipelines distintos segun si la
#: empresa nacio antes o despues de la migracion, y nadie sabria por que.
#:
#: Son un punto de partida editable, no una verdad: cada empresa las renombra,
#: reordena y agrega las suyas.
ETAPAS_POR_DEFECTO: tuple[tuple[str, str, int, str], ...] = (
    ("prospecto", "Prospecto", 0, "open"),
    ("contactado", "Contactado", 1, "open"),
    ("propuesta", "Propuesta enviada", 2, "open"),
    ("negociacion", "En negociacion", 3, "open"),
    ("ganado", "Ganado", 4, "won"),
    ("perdido", "Perdido", 5, "lost"),
)


def sembrar_etapas_por_defecto(db: Session, tenant_id: UUID) -> list[CrmStage]:
    """Le da a una empresa nueva el pipeline con el que puede empezar a vender.

    **Sin esto el CRM no funciona para ninguna empresa creada despues de la
    migracion, y no falla de forma visible.** `db/22_crm.sql` siembra las etapas
    con un `CROSS JOIN tenants`, que corre **una vez**: las empresas que ya
    existian quedaron con su pipeline y las que se dieron de alta despues, con
    cero etapas. El sintoma no se parece a la causa — el kanban se ve vacio,
    como una empresa que todavia no vende, y el primer trato responde **409**.

    Es idempotente por `code`: llamarla dos veces no duplica columnas. Eso
    importa porque tambien sirve para reparar una empresa que quedo sin etapas,
    y una reparacion que duplica es peor que el problema.
    """
    ya_estan = {
        codigo
        for codigo in db.scalars(
            select(CrmStage.code).where(
                CrmStage.tenant_id == tenant_id,
                CrmStage.deleted_at.is_(None),
            )
        ).all()
    }

    creadas: list[CrmStage] = []
    for codigo, nombre, posicion, tipo in ETAPAS_POR_DEFECTO:
        if codigo in ya_estan:
            continue
        etapa = CrmStage(
            tenant_id=tenant_id, code=codigo, name=nombre, position=posicion, kind=tipo
        )
        db.add(etapa)
        creadas.append(etapa)

    if creadas:
        db.flush()
    return creadas


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


#: Como se llama cada tipo cuando hay que explicarselo a una persona. El `kind`
#: es vocabulario del sistema; el mensaje de error lo lee quien configura.
NOMBRE_DEL_TIPO = {"open": "abierta", "won": "de ganado", "lost": "de perdido"}


def _tratos_en(db: Session, etapa: CrmStage) -> int:
    """Cuantas tarjetas vivas hay en esa columna."""
    return int(
        db.scalar(
            select(func.count(CrmDeal.id)).where(
                CrmDeal.stage_id == etapa.id,
                CrmDeal.deleted_at.is_(None),
            )
        )
        or 0
    )


def _es_la_ultima_de_su_tipo(db: Session, etapa: CrmStage, kind: str) -> bool:
    otras = [
        e
        for e in etapas_de(db, etapa.tenant_id)
        if e.kind == kind and e.id != etapa.id
    ]
    return not otras


def comprobar_cambio_de_etapa(
    db: Session, etapa: CrmStage, *, activa: bool | None, kind: str | None
) -> None:
    """Se niega a dejar el pipeline inservible, venga por `PATCH` o por `DELETE`.

    **Desactivar una etapa y retirarla hacen lo mismo**: `etapas_de` filtra por
    `active` y por `deleted_at`, asi que las dos la sacan del kanban y se llevan
    sus tratos de la vista. Cambiarle el `kind` a la unica `won` deja a la
    empresa sin forma de ganar un trato. Por eso la comprobacion es una sola y
    la llaman los dos endpoints: una guarda que solo mira el `DELETE` se salta
    con un `PATCH`, y entonces no protege nada — solo hace creer que si.

    `activa` y `kind` son **lo que se quiere dejar**, no lo que hay: `None`
    significa "no se toca". Renombrar y reordenar no pasan por ninguna guarda,
    que es lo que hace que la pantalla de configuracion sirva para algo.
    """
    se_apaga = activa is False
    cambia_de_tipo = kind is not None and kind != etapa.kind

    if se_apaga and (cuantos := _tratos_en(db, etapa)):
        raise EtapaConTratos(
            f"«{etapa.name}» todavia tiene {cuantos} oportunidad"
            f"{'es' if cuantos != 1 else ''}. Desactivarla las dejaria fuera del "
            "tablero sin borrarlas, que es peor que borrarlas: siguen en la base "
            "y nadie las ve. Muevelas a otra columna primero."
        )

    if (se_apaga or cambia_de_tipo) and _es_la_ultima_de_su_tipo(db, etapa, etapa.kind):
        tipo = NOMBRE_DEL_TIPO.get(etapa.kind, etapa.kind)
        raise UltimaEtapaDeSuTipo(
            f"«{etapa.name}» es la unica etapa {tipo} que queda. Sin ella el "
            "pipeline deja de funcionar: no se podrian crear, ganar o perder "
            "tratos segun el caso. Se puede **renombrar** y reordenar; lo que no "
            "se puede es quedarse sin ninguna de su tipo."
        )


def retirar_etapa(db: Session, etapa: CrmStage) -> None:
    """Saca una columna del pipeline, si eso no deja nada roto ni invisible.

    Es borrado logico: los tratos que pasaron por ella conservan su historia.
    """
    comprobar_cambio_de_etapa(db, etapa, activa=False, kind=None)
    etapa.deleted_at = _ahora()
    db.flush()


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

    **La columna destino tiene que estar activa.** Mover una tarjeta a una etapa
    retirada la guarda bien y la deja fuera del kanban, porque `pipeline()`
    recorre solo las activas: el trato existe en la base y no se ve en ninguna
    parte. Es la misma invisibilidad que impide retirar una etapa con tratos
    dentro, entrando por la otra puerta.
    """
    if not etapa.active or etapa.deleted_at is not None:
        raise EtapaNoDisponible(
            f"«{etapa.name}» no esta activa en el pipeline. El trato quedaria "
            "guardado y fuera del tablero, que es la peor de las dos opciones."
        )

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
