"""Una empresa nueva tiene que poder vender el mismo dia que se da de alta.

## El defecto que esto cierra

`db/22_crm.sql` siembra las etapas del pipeline con un `CROSS JOIN tenants`.
Eso corre **una vez**: las empresas que existian ese dia quedaron con sus seis
columnas, y **toda empresa dada de alta despues quedo con cero**.

Lo grave no es que falte: es que no se ve como un error.

| Lo que pasa | Como se ve |
|---|---|
| El kanban no tiene columnas | Una empresa que todavia no vende |
| El primer trato responde 409 | "el sistema esta fallando" |

Nadie lo reporta como un dato faltante, porque un pipeline vacio es un estado
legitimo. Es la misma familia que el resto de este repositorio: algo que
responde bien y no hace nada.

## Que se comprueba aca

1. Que sembrar de verdad deje el pipeline utilizable.
2. Que sea **idempotente**, porque tambien sirve para reparar una empresa que
   quedo sin etapas — y una reparacion que duplica columnas es peor.
3. Que la lista sea **la misma** que la de la migracion. Dos listas distintas
   darian pipelines distintos segun si la empresa nacio antes o despues, y
   nadie sabria por que.
4. Que el alta de empresa la llame. Es la parte que ya fallo antes en este
   repositorio: la pieza escrita, probada y sin un solo llamador.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.crm import CrmStage
from app.models.organization import Tenant
from app.routers.tenants import create_tenant
from app.schemas.organization import TenantCreate
from app.services import crm as svc

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

MIGRACION = Path(__file__).resolve().parents[3] / "db" / "22_crm.sql"


@pytest.fixture
def conexion():
    """Una transaccion que se deshace entera al terminar.

    El handler hace `commit()`, asi que la sesion se engancha con savepoints:
    su commit cierra el savepoint y la transaccion de afuera se revierte igual.
    Sin esto, cada corrida dejaria una empresa de prueba en la base.
    """
    engine = create_engine(URL)
    try:
        con = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(
            f"Sin base de datos disponible ({exc}). Esto NO comprueba las etapas "
            "por defecto: hace falta `docker compose up -d`."
        )
    trans = con.begin()
    try:
        yield con
    finally:
        trans.rollback()
        con.close()


def _sesion(con) -> Session:
    s = Session(bind=con, join_transaction_mode="create_savepoint")
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    return s


def _empresa_nueva(s: Session) -> uuid.UUID:
    """Una empresa recien creada, sin ninguna etapa. Es el estado del defecto."""
    tenant = Tenant(
        country_id=1,
        tenant_type="company",
        rut_tax_id=f"99{uuid.uuid4().int % 1_000_000:06d}-9",
        legal_name="Empresa de prueba SpA",
    )
    s.add(tenant)
    s.flush()
    svc_declarar(s, tenant.id)
    return tenant.id


def svc_declarar(s: Session, tenant_id: uuid.UUID) -> None:
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )


def _etapas(s: Session, tenant_id: uuid.UUID) -> list[CrmStage]:
    return list(
        s.scalars(
            select(CrmStage)
            .where(CrmStage.tenant_id == tenant_id, CrmStage.deleted_at.is_(None))
            .order_by(CrmStage.position)
        ).all()
    )


class TestSembrarDejaElPipelineUtilizable:
    def test_una_empresa_nueva_arranca_SIN_etapas(self, conexion) -> None:
        """La linea base del defecto. Si esta prueba falla, la base cambio y el
        resto de este archivo estaria comprobando algo que ya no pasa."""
        s = _sesion(conexion)
        tenant_id = _empresa_nueva(s)

        assert _etapas(s, tenant_id) == []

    def test_despues_de_sembrar_tiene_las_seis(self, conexion) -> None:
        s = _sesion(conexion)
        tenant_id = _empresa_nueva(s)

        svc.sembrar_etapas_por_defecto(s, tenant_id)

        assert len(_etapas(s, tenant_id)) == 6

    def test_y_YA_SE_PUEDE_crear_un_trato(self, conexion) -> None:
        """Lo que de verdad importa: antes esto lanzaba `SinEtapas`, que la API
        traduce a 409 y la pantalla muestra como un fallo del sistema."""
        s = _sesion(conexion)
        tenant_id = _empresa_nueva(s)

        with pytest.raises(svc.SinEtapas):
            svc.primera_etapa(s, tenant_id)

        svc.sembrar_etapas_por_defecto(s, tenant_id)

        assert svc.primera_etapa(s, tenant_id).kind == "open"

    def test_hay_una_de_ganado_y_una_de_perdido(self, conexion) -> None:
        """Sin `won` no se puede promover a contrato y sin `lost` no se puede
        cerrar una venta perdida con su motivo — las dos mitades de #82."""
        s = _sesion(conexion)
        tenant_id = _empresa_nueva(s)
        svc.sembrar_etapas_por_defecto(s, tenant_id)

        tipos = {e.kind for e in _etapas(s, tenant_id)}
        assert {"open", "won", "lost"} <= tipos


class TestEsIdempotente:
    def test_sembrar_dos_veces_no_duplica_columnas(self, conexion) -> None:
        s = _sesion(conexion)
        tenant_id = _empresa_nueva(s)

        svc.sembrar_etapas_por_defecto(s, tenant_id)
        svc.sembrar_etapas_por_defecto(s, tenant_id)

        assert len(_etapas(s, tenant_id)) == 6

    def test_la_segunda_vez_no_crea_nada_y_lo_dice(self, conexion) -> None:
        s = _sesion(conexion)
        tenant_id = _empresa_nueva(s)

        assert len(svc.sembrar_etapas_por_defecto(s, tenant_id)) == 6
        assert svc.sembrar_etapas_por_defecto(s, tenant_id) == []

    def test_completa_lo_que_falta_sin_tocar_lo_que_hay(self, conexion) -> None:
        """El caso de reparacion: una empresa a la que le quedo media lista.

        Renombrar una columna es lo primero que hace cualquier empresa, y una
        siembra que la pisara le borraria su configuracion.
        """
        s = _sesion(conexion)
        tenant_id = _empresa_nueva(s)
        s.add(
            CrmStage(
                tenant_id=tenant_id,
                code="ganado",
                name="Cerrado con exito",
                position=9,
                kind="won",
            )
        )
        s.flush()

        svc.sembrar_etapas_por_defecto(s, tenant_id)

        etapas = {e.code: e for e in _etapas(s, tenant_id)}
        assert len(etapas) == 6
        assert etapas["ganado"].name == "Cerrado con exito"


class TestLaListaCoincideConLaMigracion:
    """Dos listas distintas darian pipelines distintos segun cuando nacio la
    empresa, y la diferencia no se veria hasta que alguien compare dos cuentas.

    Se lee el SQL en vez de repetir los codigos aca, por el mismo motivo que la
    prueba que lee los Dockerfile: lo que se quiere fijar es que **las dos
    fuentes digan lo mismo**, y copiar la lista en la prueba solo agregaria una
    tercera que tambien se puede desincronizar.
    """

    def test_los_codigos_son_los_mismos_que_los_de_db_22(self) -> None:
        assert MIGRACION.exists(), f"No se encontro {MIGRACION}"
        sql = MIGRACION.read_text(encoding="utf-8")

        bloque = sql.split("CROSS JOIN (VALUES", 1)[1].split(") AS e(", 1)[0]
        en_el_sql = set(re.findall(r"\('([a-z]+)',", bloque))
        en_el_codigo = {codigo for codigo, _, _, _ in svc.ETAPAS_POR_DEFECTO}

        assert en_el_sql == en_el_codigo, (
            "La lista de etapas del servicio y la de `db/22_crm.sql` se "
            "separaron. Una empresa creada por la API tendria un pipeline "
            "distinto al de una creada por la migracion."
        )

    def test_hay_exactamente_una_de_ganado_y_una_de_perdido(self) -> None:
        tipos = [tipo for _, _, _, tipo in svc.ETAPAS_POR_DEFECTO]
        assert tipos.count("won") == 1
        assert tipos.count("lost") == 1

    def test_las_posiciones_no_se_repiten(self) -> None:
        """Con dos columnas en la misma posicion el orden del kanban lo decide
        el desempate por nombre, que es alfabetico y no significa nada."""
        posiciones = [p for _, _, p, _ in svc.ETAPAS_POR_DEFECTO]
        assert len(set(posiciones)) == len(posiciones)

    def test_la_primera_por_posicion_es_abierta(self) -> None:
        """`primera_etapa` prefiere la primera abierta, pero si la lista naciera
        con `perdido` arriba el kanban se leeria al reves."""
        primera = min(svc.ETAPAS_POR_DEFECTO, key=lambda e: e[2])
        assert primera[3] == "open"


class TestElAltaDeEmpresaLoHace:
    """La parte que ya fallo antes en este repositorio: la pieza existe, esta
    probada, y nadie la llama. Por eso se ejecuta el handler de verdad."""

    def test_crear_una_empresa_la_deja_con_su_pipeline(self, conexion) -> None:
        s = _sesion(conexion)

        creada = create_tenant(
            data=TenantCreate(
                country_id=1,
                rut_tax_id=f"98{uuid.uuid4().int % 1_000_000:06d}-1",
                legal_name="Constructora del Sur SpA",
            ),
            _=None,  # la guarda de Admin Global se comprueba en test_tenants_scope
            db=s,
        )

        svc_declarar(s, creada.id)
        etapas = _etapas(s, creada.id)
        assert len(etapas) == 6, (
            "El alta de empresa no siembra las etapas del CRM. La empresa queda "
            "creada y su pipeline vacio, que no se distingue de una empresa que "
            "todavia no vende."
        )

    def test_y_el_trato_se_puede_crear_recien_dada_de_alta(self, conexion) -> None:
        """La comprobacion de punta a punta: es lo que hace la pantalla."""
        s = _sesion(conexion)

        creada = create_tenant(
            data=TenantCreate(
                country_id=1,
                rut_tax_id=f"97{uuid.uuid4().int % 1_000_000:06d}-2",
                legal_name="Minera del Norte SpA",
            ),
            _=None,
            db=s,
        )

        svc_declarar(s, creada.id)
        assert svc.primera_etapa(s, creada.id).kind == "open"
