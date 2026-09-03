"""Configurar las etapas del pipeline sin dejar el CRM inservible (#78).

Las etapas son configurables por empresa a proposito: una consultora ambiental
y un gestor de residuos no venden igual. Pero el sistema **depende** de ellas, y
retirar la equivocada no rompe nada de forma visible — deja el modulo a medias
en silencio, que es la forma de falla que este repositorio persigue.

La segunda fila de la tabla de abajo se escribio primero **mal**: decia que
crear un trato responderia 409. Al medirlo resulto ser peor, y la prueba dice
exactamente lo que pasa en vez de lo que parecia razonable que pasara.

## Las tres maneras de arruinar el pipeline, medidas

| Lo que se hace | Lo que pasa | Como se ve |
|---|---|---|
| Retirar una etapa **con tratos dentro** | `pipeline()` recorre solo las activas: esos tratos **desaparecen del kanban** | Como si alguien los hubiera borrado |
| Retirar la ultima etapa `open` | `primera_etapa` cae al respaldo y el trato nuevo **nace en «Ganado», sin fecha de cierre** | Una venta ganada que nadie gano |
| Retirar la ultima etapa `won` | Ningun trato se puede promover a contrato (RF-66) | El boton simplemente no aparece nunca |

Y hay una puerta trasera que hace falta cerrar en el mismo movimiento:
`PATCH /stages/{id}` puede poner `active = false` o cambiar el `kind`, y las dos
cosas tienen **exactamente el mismo efecto** que retirar. Una guarda que solo
mira el `DELETE` es una guarda decorativa.

## Por que se exige una activa de cada tipo, incluida `lost`

`open` y `won` son evidentes: sin ellas no se puede crear ni ganar. `lost` se
trata igual porque sin una etapa de perdido no hay donde registrar una venta
perdida **con su motivo**, y aprender por que se pierde es la razon declarada de
tener un pipeline. Una empresa que no quiera esa columna puede renombrarla; lo
que no puede es quedarse sin ninguna.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.crm import CrmCompany, CrmDeal, CrmStage
from app.services import crm as svc

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    """Una empresa recien creada, con su pipeline por defecto, que se deshace.

    Se crea una empresa propia en vez de usar las del seed porque estas pruebas
    **retiran etapas**, y hacerlo sobre una empresa compartida dejaria a las
    otras pruebas corriendo contra un pipeline distinto segun el orden.
    """
    engine = create_engine(URL)
    try:
        con = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(
            f"Sin base de datos disponible ({exc}). Esto NO comprueba las guardas "
            "de las etapas: hace falta `docker compose up -d`."
        )
    trans = con.begin()
    s = Session(bind=con, join_transaction_mode="create_savepoint")
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        con.close()


@pytest.fixture
def tenant_id(db: Session) -> uuid.UUID:
    from app.models.organization import Tenant

    tenant = Tenant(
        country_id=1,
        tenant_type="company",
        rut_tax_id=f"96{uuid.uuid4().int % 1_000_000:06d}-3",
        legal_name="Empresa de prueba SpA",
    )
    db.add(tenant)
    db.flush()
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(tenant.id)}
    )
    svc.sembrar_etapas_por_defecto(db, tenant.id)
    return tenant.id


def _etapa(db: Session, tenant_id: uuid.UUID, kind: str) -> CrmStage:
    return next(e for e in svc.etapas_de(db, tenant_id) if e.kind == kind)


def _con_un_trato(db: Session, tenant_id: uuid.UUID, etapa: CrmStage) -> CrmDeal:
    empresa = CrmCompany(tenant_id=tenant_id, name="Cliente de prueba")
    db.add(empresa)
    db.flush()
    deal = CrmDeal(
        tenant_id=tenant_id,
        crm_company_id=empresa.id,
        stage_id=etapa.id,
        title="Trato de prueba",
    )
    db.add(deal)
    db.flush()
    return deal


class TestUnaEtapaConTratosNoSeRetira:
    def test_se_niega_y_dice_cuantos_hay(self, db, tenant_id) -> None:
        """El mensaje trae el numero porque la salida es moverlos, y sin saber
        cuantos son no se puede decidir si vale la pena."""
        etapa = _etapa(db, tenant_id, "open")
        _con_un_trato(db, tenant_id, etapa)

        with pytest.raises(svc.EtapaConTratos) as exc:
            svc.retirar_etapa(db, etapa)

        assert "1" in str(exc.value)

    def test_LOS_TRATOS_DESAPARECERIAN_del_kanban(self, db, tenant_id) -> None:
        """La medicion que justifica la guarda.

        Se retira la etapa saltandose el servicio —como lo hacia el endpoint— y
        se comprueba que el trato deja de aparecer en el pipeline. Sigue en la
        base: es invisible, no borrado, que es peor porque nadie lo busca.
        """
        etapa = _etapa(db, tenant_id, "open")
        deal = _con_un_trato(db, tenant_id, etapa)

        visibles_antes = {
            d.id for c in svc.pipeline(db, tenant_id)["columnas"] for d in c["deals"]
        }
        assert deal.id in visibles_antes

        etapa.deleted_at = svc._ahora()
        db.flush()

        visibles_despues = {
            d.id for c in svc.pipeline(db, tenant_id)["columnas"] for d in c["deals"]
        }
        assert deal.id not in visibles_despues
        assert db.get(CrmDeal, deal.id) is not None  # sigue existiendo

    def test_una_etapa_vacia_si_se_retira(self, db, tenant_id) -> None:
        """La otra mitad: la guarda tiene que dejar pasar el caso normal."""
        etapas = svc.etapas_de(db, tenant_id)
        # Una segunda `open` para no toparse con la guarda de la ultima.
        sobrante = next(e for e in etapas if e.kind == "open" and e.code != "prospecto")

        svc.retirar_etapa(db, sobrante)

        assert sobrante.id not in {e.id for e in svc.etapas_de(db, tenant_id)}

    def test_un_trato_ya_retirado_no_cuenta(self, db, tenant_id) -> None:
        """Un trato borrado logicamente no aparece en el kanban, asi que no hay
        nada que se pueda volver invisible."""
        etapa = _etapa(db, tenant_id, "lost")
        deal = _con_un_trato(db, tenant_id, etapa)
        deal.deleted_at = svc._ahora()
        db.flush()

        # Es la ultima `lost`, asi que la otra guarda la protege igual; lo que
        # se comprueba es que el motivo NO sea el de los tratos.
        with pytest.raises(svc.ErrorDeCrm) as exc:
            svc.retirar_etapa(db, etapa)
        assert not isinstance(exc.value, svc.EtapaConTratos)


class TestNoSePuedeQuedarSinUnTipo:
    @pytest.mark.parametrize("kind", ["open", "won", "lost"])
    def test_la_ultima_de_su_tipo_no_se_retira(self, db, tenant_id, kind) -> None:
        etapas = [e for e in svc.etapas_de(db, tenant_id) if e.kind == kind]
        # Dejar solo una de ese tipo.
        for sobrante in etapas[1:]:
            svc.retirar_etapa(db, sobrante)
        ultima = svc.etapas_de(db, tenant_id)
        ultima = [e for e in ultima if e.kind == kind]
        assert len(ultima) == 1

        with pytest.raises(svc.UltimaEtapaDeSuTipo):
            svc.retirar_etapa(db, ultima[0])

    def test_sin_etapa_abierta_un_trato_nuevo_NACE_CERRADO(self, db, tenant_id) -> None:
        """La medicion que justifica la guarda de `open`, y es peor de lo que
        parecia.

        Se esperaba un 409 —molesto pero honesto— y lo que pasa es otra cosa:
        `primera_etapa` cae a `(abiertas or etapas)[0]`, asi que sin ninguna
        columna abierta **el trato nuevo nace en la primera que haya**, que
        puede ser «Ganado». Y nace ahi sin pasar por `mover_de_etapa`, o sea
        **sin `closed_at`**: una venta ganada, sin fecha de cierre, que nadie
        gano.

        El respaldo esta bien puesto —vale para una empresa que renombro sus
        columnas y dejo el orden raro—; lo que no puede pasar es quedarse sin
        ninguna abierta, y de eso se encarga la guarda.
        """
        for abierta in [e for e in svc.etapas_de(db, tenant_id) if e.kind == "open"]:
            abierta.deleted_at = svc._ahora()
        db.flush()

        empresa = CrmCompany(tenant_id=tenant_id, name="Cliente de prueba")
        db.add(empresa)
        db.flush()
        deal = svc.crear_deal(
            db, tenant_id, {"crm_company_id": empresa.id, "title": "Recien creado"}
        )

        etapa = db.get(CrmStage, deal.stage_id)
        assert etapa is not None and etapa.kind != "open"
        assert deal.closed_at is None, (
            "El trato nace en una columna de cierre y sin fecha de cierre: las "
            "metricas lo cuentan como ganado y el ciclo de venta no se puede medir."
        )

    def test_el_mensaje_explica_la_salida(self, db, tenant_id) -> None:
        """Sin decir que se puede renombrar, la unica lectura posible es que el
        sistema no deja configurar el pipeline."""
        abiertas = [e for e in svc.etapas_de(db, tenant_id) if e.kind == "open"]
        for sobrante in abiertas[1:]:
            svc.retirar_etapa(db, sobrante)

        with pytest.raises(svc.UltimaEtapaDeSuTipo) as exc:
            svc.retirar_etapa(db, abiertas[0])

        assert "renombrar" in str(exc.value).lower()


class TestLaPuertaTraseraDelPatch:
    """`active = false` y cambiar el `kind` tienen el mismo efecto que retirar.

    Una guarda que solo mira el `DELETE` se salta con un `PATCH`, y entonces no
    protege nada — solo hace creer que si.
    """

    def test_desactivar_la_ultima_abierta_se_niega(self, db, tenant_id) -> None:
        abiertas = [e for e in svc.etapas_de(db, tenant_id) if e.kind == "open"]
        for sobrante in abiertas[1:]:
            svc.retirar_etapa(db, sobrante)

        with pytest.raises(svc.UltimaEtapaDeSuTipo):
            svc.comprobar_cambio_de_etapa(db, abiertas[0], activa=False, kind=None)

    def test_cambiarle_el_tipo_a_la_ultima_ganada_se_niega(self, db, tenant_id) -> None:
        """Pasar la unica `won` a `open` deja a la empresa sin forma de ganar."""
        ganada = _etapa(db, tenant_id, "won")

        with pytest.raises(svc.UltimaEtapaDeSuTipo):
            svc.comprobar_cambio_de_etapa(db, ganada, activa=None, kind="open")

    def test_desactivar_una_etapa_CON_TRATOS_tambien_se_niega(
        self, db, tenant_id
    ) -> None:
        """Sus tratos desaparecerian del kanban igual que al retirarla."""
        etapa = _etapa(db, tenant_id, "open")
        _con_un_trato(db, tenant_id, etapa)

        with pytest.raises(svc.EtapaConTratos):
            svc.comprobar_cambio_de_etapa(db, etapa, activa=False, kind=None)

    def test_renombrar_y_reordenar_NO_se_tocan(self, db, tenant_id) -> None:
        """La otra mitad, y la mas importante para que la pantalla sirva:
        cambiar el nombre o la posicion no toca ninguna guarda."""
        etapa = _etapa(db, tenant_id, "won")

        svc.comprobar_cambio_de_etapa(db, etapa, activa=None, kind=None)
        svc.comprobar_cambio_de_etapa(db, etapa, activa=True, kind="won")

    def test_cambiar_el_tipo_de_UNA_DE_VARIAS_se_permite(self, db, tenant_id) -> None:
        """Con cuatro etapas abiertas, pasar una a `lost` no deja sin abiertas."""
        abierta = _etapa(db, tenant_id, "open")

        svc.comprobar_cambio_de_etapa(db, abierta, activa=None, kind="lost")


class TestMoverAUnaEtapaRetirada:
    def test_no_se_puede_mover_un_trato_a_una_columna_inactiva(
        self, db, tenant_id
    ) -> None:
        """Es la misma invisibilidad por la otra puerta: el trato se guarda y
        no aparece en ninguna columna del kanban."""
        origen = _etapa(db, tenant_id, "open")
        deal = _con_un_trato(db, tenant_id, origen)
        destino = next(
            e for e in svc.etapas_de(db, tenant_id) if e.kind == "open" and e.id != origen.id
        )
        destino.active = False
        db.flush()

        with pytest.raises(svc.EtapaNoDisponible):
            svc.mover_de_etapa(db, deal, destino)

    def test_a_una_activa_se_mueve_igual_que_siempre(self, db, tenant_id) -> None:
        origen = _etapa(db, tenant_id, "open")
        deal = _con_un_trato(db, tenant_id, origen)
        destino = _etapa(db, tenant_id, "won")

        svc.mover_de_etapa(db, deal, destino)

        assert deal.stage_id == destino.id
        assert deal.closed_at is not None


class TestLosDosEndpointsLaLLAMAN:
    """La guarda existe y esta probada — y eso no basta.

    La mutacion que la desconecta del `PATCH` no hacia fallar ninguna prueba,
    porque todas llamaban al servicio directo. Es exactamente el patron que este
    repositorio viene persiguiendo: la pieza escrita, probada, y sin nadie que la
    use. Estas dos ejecutan los endpoints de verdad.
    """

    def test_el_PATCH_no_puede_desactivar_la_ultima_de_su_tipo(
        self, db, tenant_id
    ) -> None:
        from fastapi import HTTPException

        from app.routers.crm import update_stage
        from app.schemas.crm import CrmStageUpdate

        ganada = _etapa(db, tenant_id, "won")

        with pytest.raises(HTTPException) as exc:
            update_stage(ganada.id, CrmStageUpdate(active=False), db=db)

        assert exc.value.status_code == 409

    def test_el_DELETE_no_puede_retirar_una_etapa_con_tratos(
        self, db, tenant_id
    ) -> None:
        from fastapi import HTTPException

        from app.routers.crm import delete_stage

        etapa = _etapa(db, tenant_id, "open")
        _con_un_trato(db, tenant_id, etapa)

        with pytest.raises(HTTPException) as exc:
            delete_stage(etapa.id, db=db)

        assert exc.value.status_code == 409

    def test_y_renombrar_por_el_PATCH_sigue_funcionando(self, db, tenant_id) -> None:
        """La otra mitad: si la guarda bloqueara tambien lo normal, la pantalla
        de configuracion no serviria para nada."""
        from app.routers.crm import update_stage
        from app.schemas.crm import CrmStageUpdate

        etapa = _etapa(db, tenant_id, "won")

        actualizada = update_stage(
            etapa.id, CrmStageUpdate(name="Cerrado con exito", position=7), db=db
        )

        assert actualizada.name == "Cerrado con exito"
        assert actualizada.position == 7
