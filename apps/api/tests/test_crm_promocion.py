"""Promover un trato ganado a contrato (#82, RF-66).

Es el punto donde el CRM deja de ser una lista aparte y se conecta con el
sistema: la venta cerrada pasa a ser la relacion que se presta. Por eso lo que
importa no es tanto lo que hace —guardar un id— sino **lo que se niega a
hacer**, que es donde se rompe la lista de clientes:

1. **Promover un trato que no se gano.** Un contrato colgando de un trato en
   negociacion, o perdido, hace que la lista de clientes cuente a alguien que
   no lo es.
2. **Mover el enlace a otro contrato.** Deja el anterior sin la venta que lo
   origino, y la trazabilidad comercial rota.
3. **Enlazar con el contrato de otro cliente.** Deja la ficha de una empresa
   apuntando a la relacion comercial de otra.

Va contra la base real, como el resto del CRM: `contract_id` es una clave
foranea, y **las claves foraneas no pasan por RLS**.
"""
from __future__ import annotations

import itertools
import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.crm import CrmCompany, CrmDeal, CrmStage
from app.models.organization import Contract
from app.services import crm as svc

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EMPRESA_B = uuid.UUID("a0000000-0000-0000-0000-000000000002")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

_NUMERO = itertools.count(1000)


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    s = Session(bind=conexion)
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA_A)}
    )
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


def _empresa(db: Session, nombre: str = "Prospecto de promocion") -> CrmCompany:
    fila = CrmCompany(tenant_id=EMPRESA_A, name=nombre)
    db.add(fila)
    db.flush()
    return fila


def _etapa(db: Session, kind: str) -> CrmStage:
    fila = db.scalars(
        select(CrmStage)
        .where(
            CrmStage.tenant_id == EMPRESA_A,
            CrmStage.kind == kind,
            CrmStage.active.is_(True),
            CrmStage.deleted_at.is_(None),
        )
        .order_by(CrmStage.position)
    ).first()
    if fila is None:
        pytest.skip(f"El seed no dejo una etapa de tipo {kind}")
    return fila


def _contrato(db: Session, cliente: uuid.UUID = EMPRESA_B) -> Contract:
    """Un contrato de esta empresa, con `cliente` del otro lado.

    `ck_contracts_partes` exige que las dos partes sean distintas: un contrato
    consigo misma no es un contrato.
    """
    fila = Contract(
        tenant_id=EMPRESA_A,
        manager_tenant_id=EMPRESA_A,
        client_tenant_id=cliente,
        contract_number=f"PRUEBA-{next(_NUMERO)}",
        title="Servicio de cumplimiento",
        status="active",
        start_date=date(2026, 1, 1),
    )
    db.add(fila)
    db.flush()
    return fila


def _trato(db: Session, empresa: CrmCompany) -> CrmDeal:
    return svc.crear_deal(
        db,
        EMPRESA_A,
        {
            "crm_company_id": empresa.id,
            "title": "Implantacion Ambienta",
            "amount": Decimal("5000000"),
            "currency": "CLP",
        },
    )


def _ganado(db: Session, empresa: CrmCompany) -> tuple[CrmDeal, CrmStage]:
    deal = _trato(db, empresa)
    etapa = _etapa(db, "won")
    svc.mover_de_etapa(db, deal, etapa)
    return deal, etapa


class TestPromoverUnTratoGanado:
    def test_el_trato_queda_enlazado_al_contrato(self, db: Session) -> None:
        empresa = _empresa(db)
        deal, etapa = _ganado(db, empresa)
        contrato = _contrato(db)

        efectos = svc.promover_a_contrato(db, deal, contrato, etapa)

        assert deal.contract_id == contrato.id
        assert any("enlazado" in e for e in efectos)

    def test_la_ficha_deja_de_ser_un_PROSPECTO(self, db: Session) -> None:
        """La razon de que esto sea un endpoint y no un `PATCH` del id.

        Sin este paso, la empresa que ya firmo sigue apareciendo en el embudo
        como alguien a quien hay que venderle.
        """
        empresa = _empresa(db)
        assert empresa.status == "prospect"
        deal, etapa = _ganado(db, empresa)

        svc.promover_a_contrato(db, deal, _contrato(db), etapa)

        assert empresa.status == "client"

    def test_la_ficha_queda_ligada_al_TENANT_del_contrato(self, db: Session) -> None:
        """`client_tenant_id` es el puente entre el prospecto y el cliente real.

        Y **no se acepta del cuerpo**: sale del contrato, que ya nombra a las
        dos partes y esta acotado por RLS. Aceptarlo dejaria a una empresa
        ligar su ficha con el tenant de otra.
        """
        empresa = _empresa(db)
        assert empresa.client_tenant_id is None
        deal, etapa = _ganado(db, empresa)
        contrato = _contrato(db, cliente=EMPRESA_B)

        svc.promover_a_contrato(db, deal, contrato, etapa)

        assert empresa.client_tenant_id == EMPRESA_B

    def test_se_dice_todo_lo_que_paso(self, db: Session) -> None:
        empresa = _empresa(db)
        deal, etapa = _ganado(db, empresa)

        efectos = svc.promover_a_contrato(db, deal, _contrato(db), etapa)

        assert len(efectos) == 3, f"faltan efectos por anunciar: {efectos}"


class TestLoQueSeNiegaAHacer:
    def test_un_trato_ABIERTO_no_se_promueve(self, db: Session) -> None:
        """La lista de clientes contando a alguien que todavia no lo es."""
        empresa = _empresa(db)
        deal = _trato(db, empresa)
        abierta = db.get(CrmStage, deal.stage_id)

        with pytest.raises(svc.TratoNoGanado):
            svc.promover_a_contrato(db, deal, _contrato(db), abierta)

    def test_un_trato_PERDIDO_tampoco(self, db: Session) -> None:
        """Y este es el que `closed_at` por si solo no distingue.

        Perder tambien cierra el trato. Mirando solo la fecha de cierre, un
        trato perdido pasaria por ganado.
        """
        empresa = _empresa(db)
        deal = _trato(db, empresa)
        perdida = _etapa(db, "lost")
        svc.mover_de_etapa(db, deal, perdida, "eligieron a la competencia")
        assert deal.closed_at is not None

        with pytest.raises(svc.TratoNoGanado):
            svc.promover_a_contrato(db, deal, _contrato(db), perdida)

    def test_no_se_puede_MOVER_el_enlace_a_otro_contrato(self, db: Session) -> None:
        """Dejaria el contrato anterior sin la venta que lo origino."""
        empresa = _empresa(db)
        deal, etapa = _ganado(db, empresa)
        primero = _contrato(db)
        svc.promover_a_contrato(db, deal, primero, etapa)

        with pytest.raises(svc.YaPromovido):
            svc.promover_a_contrato(db, deal, _contrato(db), etapa)

        assert deal.contract_id == primero.id, "el enlace se movio igual"

    def test_repetir_con_el_MISMO_contrato_no_falla(self, db: Session) -> None:
        """Es la misma operacion otra vez, no una distinta.

        Un doble clic, o un reintento tras un timeout, no puede terminar en un
        409 que haga dudar de si la promocion quedo hecha.
        """
        empresa = _empresa(db)
        deal, etapa = _ganado(db, empresa)
        contrato = _contrato(db)
        svc.promover_a_contrato(db, deal, contrato, etapa)

        efectos = svc.promover_a_contrato(db, deal, contrato, etapa)

        assert deal.contract_id == contrato.id
        # Y no vuelve a anunciar lo que ya estaba hecho.
        assert efectos == []

    def test_un_contrato_de_OTRO_cliente_se_rechaza(self, db: Session) -> None:
        """La ficha ya nombra a un tenant; el contrato nombra a otro.

        Alguien se equivoco de contrato, y aceptarlo dejaria la ficha de una
        empresa apuntando a la relacion comercial de otra.
        """
        empresa = _empresa(db)
        # La ficha ya nombra a un tenant...
        empresa.client_tenant_id = EMPRESA_A
        db.flush()
        deal, etapa = _ganado(db, empresa)

        # ...y el contrato nombra a otro distinto. `ck_contracts_partes` impide
        # que un contrato tenga la misma empresa de los dos lados, asi que el
        # desencuentro se arma con los dos tenants que existen.
        otro = _contrato(db, cliente=EMPRESA_B)

        with pytest.raises(svc.ClienteDistinto):
            svc.promover_a_contrato(db, deal, otro, etapa)

        assert deal.contract_id is None, "quedo enlazado pese al rechazo"
