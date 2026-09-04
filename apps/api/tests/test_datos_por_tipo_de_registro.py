"""El tipo de un registro de mejora decide que datos exige la norma (#37).

El spec de `gestion-mejoras`:

> El sistema SHALL pedir los datos que la norma exige segun el tipo de registro,
> y SHALL rechazar un registro al que le falten los de su tipo.
>
> - Salida no conforme sin producto -> el sistema la rechaza
> - Reclamo sin cliente -> el sistema lo rechaza

## Lo que habia antes

`record_type` y `detection_origin` existian con su CHECK desde el principio, con
los cinco valores de cada uno. Lo que **no** existia era donde guardar lo que
cada tipo pide, ni nada que lo exigiera: se podia registrar una salida no
conforme sin decir que producto ni que lote, y quedaba idéntica a una bien
registrada en cualquier listado.

Es la version en datos del patron de siempre: la clasificacion declarada y sin
consecuencias.

## Dos barreras y por que las dos

`db/24` pone las restricciones en la base, que es la que no se puede saltar — un
`UPDATE` a mano tambien tiene que respetarlas, y el registro de mejora es de las
tablas que alguien corrige por SQL cuando algo sale mal.

El schema las comprueba antes para responder un **422 legible** en vez de un
error de restriccion, que se lee como un fallo del sistema y no como un dato que
falta.

Este archivo prueba **las dos**, porque protegen cosas distintas y una puede
caerse sin la otra.
"""
from __future__ import annotations

import os
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.audit import Nonconformity
from app.schemas.audit import NonconformityCreate

EMPRESA = uuid.UUID("a0000000-0000-0000-0000-000000000001")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


def _alta(**extra) -> NonconformityCreate:
    base = dict(code="PRB-1", title="t", description="d", severity="major")
    return NonconformityCreate(**{**base, **extra})


# ── La barrera legible: el schema ─────────────────────────────────────────


class TestUnaSalidaNoConformeExigeSuProducto:
    """ISO 9001 8.7: la salida no conforme se identifica y se controla. Sin
    producto y lote no se sabe **que** se controlo."""

    def test_sin_producto_se_rechaza(self) -> None:
        with pytest.raises(ValidationError, match="salida_no_conforme"):
            _alta(record_type="salida_no_conforme")

    def test_sin_lote_tampoco(self) -> None:
        with pytest.raises(ValidationError, match="lote"):
            _alta(record_type="salida_no_conforme", product_data={"sku": "A-1"})

    def test_un_sku_en_blanco_no_cuenta_como_sku(self) -> None:
        """Un espacio pasa cualquier comprobacion de presencia y no identifica
        nada. Es la forma mas facil de saltarse el requisito sin querer."""
        with pytest.raises(ValidationError):
            _alta(
                record_type="salida_no_conforme",
                product_data={"sku": "   ", "lote": "L-9"},
            )

    def test_con_sku_y_lote_se_acepta(self) -> None:
        registro = _alta(
            record_type="salida_no_conforme",
            product_data={"sku": "A-1", "lote": "L-9", "cantidad": 12},
        )
        assert registro.product_data["lote"] == "L-9"


class TestUnReclamoExigeSuCliente:
    """ISO 9001 9.1.2: un reclamo es informacion sobre la percepcion del
    cliente. Sin cliente ni canal no es un reclamo, es una nota."""

    def test_sin_cliente_se_rechaza(self) -> None:
        with pytest.raises(ValidationError, match="reclamo"):
            _alta(record_type="reclamo")

    def test_sin_canal_tampoco(self) -> None:
        with pytest.raises(ValidationError, match="canal"):
            _alta(record_type="reclamo", complaint_data={"cliente_nombre": "ACME"})

    def test_con_cliente_y_canal_se_acepta(self) -> None:
        assert _alta(
            record_type="reclamo",
            complaint_data={"cliente_nombre": "ACME", "canal": "correo"},
        ).complaint_data["canal"] == "correo"


class TestLosDatosDeUnTipoNoSeCuelanEnOtro:
    """La otra mitad, y la que no pide el spec en palabras pero se sigue de el.

    Un reclamo con datos de producto es un registro mal clasificado, y en
    cualquier listado **se ve exactamente igual que uno bien hecho**. Sin esta
    comprobacion el tipo deja de significar algo.
    """

    def test_un_reclamo_con_datos_de_producto_se_rechaza(self) -> None:
        with pytest.raises(ValidationError, match="product_data"):
            _alta(
                record_type="reclamo",
                complaint_data={"cliente_nombre": "A", "canal": "c"},
                product_data={"sku": "A", "lote": "L"},
            )

    def test_una_no_conformidad_con_datos_de_reclamo_tambien(self) -> None:
        with pytest.raises(ValidationError, match="complaint_data"):
            _alta(
                record_type="no_conformidad",
                complaint_data={"cliente_nombre": "A", "canal": "c"},
            )

    def test_un_riesgo_no_lleva_ninguno_de_los_dos(self) -> None:
        assert _alta(record_type="riesgo").product_data is None


class TestElOrigenDeAuditoriaExigeSuHallazgo:
    """Sin el hallazgo no hay trazabilidad hacia la auditoria que lo origino, y
    eso es lo primero que se pide al revisar el seguimiento de una auditoria."""

    @pytest.mark.parametrize("origen", ["auditoria_interna", "auditoria_externa"])
    def test_sin_hallazgo_se_rechaza(self, origen: str) -> None:
        with pytest.raises(ValidationError, match="hallazgo"):
            _alta(detection_origin=origen)

    def test_con_hallazgo_se_acepta(self) -> None:
        assert _alta(
            detection_origin="auditoria_interna", audit_item_id=uuid.uuid4()
        ).audit_item_id is not None

    @pytest.mark.parametrize("origen", ["interna", "externa", "analisis_foda"])
    def test_los_origenes_que_no_son_auditoria_no_lo_exigen(self, origen: str) -> None:
        """Un encargado que detecta una debilidad sin auditoria de por medio la
        registra igual: el spec lo pide explicito."""
        assert _alta(detection_origin=origen).audit_item_id is None


class TestUnRegistroSinTipoSigueSiendoValido:
    def test_sin_tipo_no_se_exige_nada(self) -> None:
        """Las filas historicas no declaran tipo. Esta migracion **no inventa**
        el tipo de un registro que nadie clasifico: deducirlo seria escribir una
        clasificacion que no hizo ninguna persona, en la tabla que un auditor
        lee."""
        assert _alta().record_type is None


# ── La barrera que no se puede saltar: la base ────────────────────────────


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        con = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(
            f"Sin base de datos disponible ({exc}). Esto NO comprueba las "
            "restricciones de `db/24`: hace falta `docker compose up -d`."
        )
    trans = con.begin()
    s = Session(bind=con, join_transaction_mode="create_savepoint")
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA)}
    )
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        con.close()


def _insertar(db: Session, **extra) -> None:
    """Escribe saltandose Pydantic, que es lo que hace un `UPDATE` a mano."""
    nc = Nonconformity(
        tenant_id=EMPRESA,
        code=f"PRB-{uuid.uuid4().hex[:8].upper()}",
        title="t",
        description="d",
        severity="major",
        status="open",
        **extra,
    )
    db.add(nc)
    db.flush()


class TestLaBaseTambienLoExige:
    """Saltandose el schema, que es exactamente lo que hace quien corrige por SQL.

    Si estas pruebas caen, la unica barrera que queda es Pydantic — y entonces
    cualquier escritura que no pase por la API deja datos que la norma no admite.
    """

    def test_salida_no_conforme_sin_producto_la_rechaza_la_base(self, db) -> None:
        with pytest.raises(Exception, match="ck_nc_salida_con_producto"):
            _insertar(db, record_type="salida_no_conforme")

    def test_reclamo_sin_cliente_la_rechaza_la_base(self, db) -> None:
        with pytest.raises(Exception, match="ck_nc_reclamo_con_cliente"):
            _insertar(db, record_type="reclamo")

    def test_origen_de_auditoria_sin_hallazgo_la_rechaza_la_base(self, db) -> None:
        with pytest.raises(Exception, match="ck_nc_auditoria_con_hallazgo"):
            _insertar(db, detection_origin="auditoria_externa")

    def test_datos_de_un_tipo_en_otro_los_rechaza_la_base(self, db) -> None:
        with pytest.raises(Exception, match="ck_nc_datos_del_tipo_que_es"):
            _insertar(
                db,
                record_type="no_conformidad",
                product_data={"sku": "A", "lote": "L"},
            )

    def test_y_un_registro_bien_formado_entra(self, db) -> None:
        """La otra mitad: las restricciones no pueden volverse imposibles de
        satisfacer."""
        _insertar(
            db,
            record_type="salida_no_conforme",
            product_data={"sku": "A-1", "lote": "L-9", "nombre": "Envase"},
        )

    def test_las_filas_que_ya_existian_siguen_valias(self, db) -> None:
        """La migracion se aplico sobre datos reales sin tipo declarado. Si las
        restricciones no admitieran `record_type IS NULL`, aplicarla habria
        fallado — y sobre una base con datos de un cliente, a mitad de camino."""
        assert db.scalar(text("SELECT count(*) FROM nonconformities")) >= 0
        _insertar(db, record_type=None)
