"""El CRM: pipeline, actividades y aislamiento (epica #32).

## Lo que estas pruebas protegen

1. **Que el pipeline no mienta.** Los totales se calculan sobre todo lo que
   hay, no sobre las tarjetas que se devuelven. Con una columna pasada del
   tope, sumar lo visible daria un monto menor que el real — y ese numero se
   cita despues en una reunion como si fuera el pipeline completo.
2. **Que mover de columna haga lo que corresponde.** Ganar y perder cierran el
   trato; volver a una etapa abierta lo reabre **y limpia el cierre**, o
   quedaria un trato activo con fecha de cierre y las metricas lo contarian de
   los dos lados.
3. **Que perder exija motivo.** La razon de tener un pipeline es aprender por
   que se pierde.
4. **Que una empresa no vea ni toque el CRM de otra** (#83). Va contra la base
   real: lo que protege es Row Level Security, no un `if`, y eso no se puede
   comprobar con una sesion simulada.
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.crm import CrmCompany, CrmDeal, CrmStage
from app.services import crm as svc

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


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
        # Todo se deshace: estas pruebas escriben en tablas vivas.
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


def _empresa(db: Session, nombre: str = "Prospecto de prueba") -> CrmCompany:
    fila = CrmCompany(tenant_id=EMPRESA_A, name=nombre)
    db.add(fila)
    db.flush()
    return fila


def _etapa(db: Session, kind: str) -> CrmStage:
    """La primera etapa activa de ese tipo."""
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


def _trato(
    db: Session, empresa: CrmCompany, monto: str | None = None, moneda: str = "CLP"
) -> CrmDeal:
    return svc.crear_deal(
        db,
        EMPRESA_A,
        {
            "crm_company_id": empresa.id,
            "title": "Implantacion Ambienta",
            "amount": Decimal(monto) if monto else None,
            "currency": moneda,
        },
    )


def _monto(columna: dict, moneda: str = "CLP") -> Decimal:
    """Lo que suma una columna en una moneda. Cero si esa moneda no aparece."""
    return next((t for m, t in columna["montos"] if m == moneda), Decimal("0"))


def _monedas(columna: dict) -> list[str]:
    return [m for m, _ in columna["montos"]]


class TestLasEtapasPorDefecto:
    def test_toda_empresa_nace_con_pipeline(self, db: Session) -> None:
        """Un pipeline sin etapas no se puede dibujar.

        Mismo criterio que `09_roles_por_codigo.sql`: lo que toda empresa
        necesita para que la pantalla funcione se crea en todas, no solo en la
        de demostracion.
        """
        etapas = svc.etapas_de(db, EMPRESA_A)
        assert len(etapas) >= 4
        assert [e.kind for e in etapas if e.kind == "won"], "falta una etapa de ganado"
        assert [e.kind for e in etapas if e.kind == "lost"], "falta una etapa de perdido"

    def test_vienen_en_su_orden(self, db: Session) -> None:
        etapas = svc.etapas_de(db, EMPRESA_A)
        assert [e.position for e in etapas] == sorted(e.position for e in etapas)

    def test_un_trato_nuevo_cae_en_la_primera_ABIERTA(self, db: Session) -> None:
        """Y no en la primera a secas.

        Si alguien reordena y deja "Perdido" arriba, un trato nuevo naceria
        perdido — con su fecha de cierre y todo.
        """
        db.execute(
            text(
                "UPDATE crm_stages SET position = -1 "
                "WHERE tenant_id = :t AND kind = 'lost'"
            ),
            {"t": str(EMPRESA_A)},
        )
        db.expire_all()

        deal = _trato(db, _empresa(db))

        etapa = db.get(CrmStage, deal.stage_id)
        assert etapa.kind == "open", "el trato nacio en una etapa de cierre"
        assert deal.closed_at is None


class TestMoverDeEtapa:
    def test_ganar_cierra_el_trato(self, db: Session) -> None:
        deal = _trato(db, _empresa(db))
        efectos = svc.mover_de_etapa(db, deal, _etapa(db, "won"))

        assert deal.closed_at is not None, (
            "sin `closed_at` no se puede medir cuanto dura un ciclo de venta"
        )
        assert any("cerrado" in e for e in efectos)

    def test_perder_SIN_motivo_se_rechaza(self, db: Session) -> None:
        """La razon de tener un pipeline es aprender por que se pierde."""
        deal = _trato(db, _empresa(db))
        with pytest.raises(svc.MotivoRequerido):
            svc.mover_de_etapa(db, deal, _etapa(db, "lost"))

    def test_perder_con_motivo_en_blanco_tampoco(self, db: Session) -> None:
        deal = _trato(db, _empresa(db))
        with pytest.raises(svc.MotivoRequerido):
            svc.mover_de_etapa(db, deal, _etapa(db, "lost"), "   ")

    def test_perder_guarda_el_motivo(self, db: Session) -> None:
        deal = _trato(db, _empresa(db))
        svc.mover_de_etapa(db, deal, _etapa(db, "lost"), "el cliente eligio a la competencia")

        assert deal.lost_reason == "el cliente eligio a la competencia"
        assert deal.closed_at is not None

    def test_reabrir_LIMPIA_el_cierre(self, db: Session) -> None:
        """La prueba que evita contar el mismo trato dos veces.

        Sin limpiar `closed_at`, un trato reabierto queda activo **y** con
        fecha de cierre: aparece en los pendientes y en las metricas de cierre
        del mes pasado a la vez.
        """
        deal = _trato(db, _empresa(db))
        svc.mover_de_etapa(db, deal, _etapa(db, "lost"), "se enfrio")
        assert deal.closed_at is not None

        efectos = svc.mover_de_etapa(db, deal, _etapa(db, "open"))

        assert deal.closed_at is None
        assert deal.lost_reason is None, "quedo el motivo de una perdida que ya no existe"
        assert any("reabrio" in e for e in efectos)

    def test_mover_entre_abiertas_no_cierra_nada(self, db: Session) -> None:
        deal = _trato(db, _empresa(db))
        abiertas = [e for e in svc.etapas_de(db, EMPRESA_A) if e.kind == "open"]
        if len(abiertas) < 2:
            pytest.skip("Hace falta mas de una etapa abierta")

        svc.mover_de_etapa(db, deal, abiertas[1])

        assert deal.stage_id == abiertas[1].id
        assert deal.closed_at is None


class TestElPipeline:
    def test_devuelve_una_columna_por_etapa_activa(self, db: Session) -> None:
        datos = svc.pipeline(db, EMPRESA_A)
        activas = svc.etapas_de(db, EMPRESA_A)
        assert len(datos["columnas"]) == len(activas)

    def test_los_totales_se_calculan_sobre_TODO_lo_que_hay(self, db: Session) -> None:
        """No sobre las tarjetas devueltas.

        Es la afirmacion que impide que el monto del pipeline sea menor que el
        real en cuanto una columna pase del tope — y ese numero se cita despues
        en una reunion como si fuera el pipeline completo.
        """
        empresa = _empresa(db)
        _trato(db, empresa, "1000000")
        _trato(db, empresa, "500000")
        db.flush()

        datos = svc.pipeline(db, EMPRESA_A)
        primera = svc.primera_etapa(db, EMPRESA_A)
        columna = next(c for c in datos["columnas"] if c["stage"].id == primera.id)

        assert columna["total_deals"] >= 2
        assert _monto(columna) >= Decimal("1500000")

    def test_un_trato_sin_monto_no_INVENTA_un_cero(self, db: Session) -> None:
        """`amount` es opcional: hay tratos que arrancan sin cifra.

        Y esa columna **no** declara "CLP 0". Un trato al que todavia no le
        pusieron valor no es un trato de cero pesos, y la columna diciendo cero
        se lee como que ya se valoro y no vale nada.

        **La etapa se crea aca a proposito.** La primera version usaba la
        primera etapa del pipeline y afirmaba `montos == []`, lo que solo era
        cierto mientras la base no tuviera ningun otro trato; en cuanto se
        sembraron datos de demostracion, la prueba empezo a fallar por una razon
        que no tenia que ver con lo que mide. Peor todavia: con otro trato
        valorado en la misma columna, la afirmacion tampoco distinguiria el
        cero inventado, porque la suma del grupo ya no seria nula. Una columna
        propia es lo unico que deja la afirmacion exacta.
        """
        etapa = CrmStage(
            tenant_id=EMPRESA_A,
            code="solo-sin-valorar",
            name="Solo sin valorar",
            position=99,
            kind="open",
        )
        db.add(etapa)
        db.flush()

        empresa = _empresa(db)
        svc.crear_deal(
            db,
            EMPRESA_A,
            {"crm_company_id": empresa.id, "title": "Sin cifra", "currency": "CLP"},
            stage_id=etapa.id,
        )
        db.flush()

        datos = svc.pipeline(db, EMPRESA_A)
        columna = next(c for c in datos["columnas"] if c["stage"].id == etapa.id)

        assert columna["total_deals"] == 1, "el trato sin monto no se conto"
        # Exacto y no `all(... is not None)`: esa version pasaba igual con una
        # entrada `("CLP", 0)`, que es justo lo que no debe existir.
        assert columna["montos"] == [], (
            "la columna declaro un total para un trato que nadie ha valorado"
        )

    def test_DOS_MONEDAS_no_se_suman_entre_si(self, db: Session) -> None:
        """La prueba que faltaba, y el numero que se cita en una reunion.

        `currency` es un campo por trato y **ningun CHECK lo fija en una sola**.
        Sumando a secas, una columna con 1.000 CLP y 1.000 USD informaba
        `2000` — que no es plata de ninguna clase. Lo peor no es el error de
        cambio: es que `2000` se ve razonable, asi que nadie lo vuelve a mirar.
        """
        empresa = _empresa(db)
        _trato(db, empresa, "1000", "CLP")
        _trato(db, empresa, "7", "USD")
        db.flush()

        datos = svc.pipeline(db, EMPRESA_A)
        primera = svc.primera_etapa(db, EMPRESA_A)
        columna = next(c for c in datos["columnas"] if c["stage"].id == primera.id)

        # Los montos van distintos a proposito: con 1.000 y 1.000 la prueba
        # pasaria igual sumandolos mal en una de las dos entradas.
        assert "USD" in _monedas(columna), "la moneda extranjera desaparecio"
        assert "CLP" in _monedas(columna)
        assert _monto(columna, "USD") == Decimal("7"), (
            "el total en USD arrastro pesos"
        )
        # Y ninguna entrada trae la suma cruda de las dos, que es el 1007 que
        # informaba la version anterior.
        assert all(
            total != Decimal("1007") for _, total in columna["montos"]
        ), "alguna entrada sumo las dos monedas entre si"

    def test_cada_moneda_aparece_UNA_sola_vez(self, db: Session) -> None:
        """Dos entradas 'CLP' en la misma columna serian dos totales parciales.

        La pantalla mostraria "CLP 1.000" y debajo "CLP 500" para la misma
        columna, y quien lo lea tiene que sumar a mano — que es exactamente el
        trabajo que este endpoint existe para evitar.
        """
        empresa = _empresa(db)
        _trato(db, empresa, "1000", "CLP")
        _trato(db, empresa, "500", "CLP")
        db.flush()

        for columna in svc.pipeline(db, EMPRESA_A)["columnas"]:
            monedas = _monedas(columna)
            assert len(monedas) == len(set(monedas)), f"moneda repetida: {monedas}"

    def test_el_CONTEO_si_junta_las_monedas(self, db: Session) -> None:
        """Contar tratos no depende de la moneda; sumar plata si.

        Es la mitad que se rompe sola al agrupar por moneda: si `total_deals`
        se tomara de una de las filas agrupadas en vez de sumarlas, una columna
        con un trato en CLP y otro en USD informaria **un** trato.
        """
        empresa = _empresa(db)
        primera = svc.primera_etapa(db, EMPRESA_A)
        antes = next(
            c["total_deals"]
            for c in svc.pipeline(db, EMPRESA_A)["columnas"]
            if c["stage"].id == primera.id
        )
        _trato(db, empresa, "1000", "CLP")
        _trato(db, empresa, "1000", "USD")
        db.flush()

        despues = next(
            c["total_deals"]
            for c in svc.pipeline(db, EMPRESA_A)["columnas"]
            if c["stage"].id == primera.id
        )
        assert despues == antes + 2, "las dos monedas se contaron como un trato"

    def test_los_borrados_no_cuentan(self, db: Session) -> None:
        empresa = _empresa(db)
        deal = _trato(db, empresa, "999")
        db.flush()
        antes = svc.pipeline(db, EMPRESA_A)
        primera = svc.primera_etapa(db, EMPRESA_A)
        total_antes = next(
            c["total_deals"] for c in antes["columnas"] if c["stage"].id == primera.id
        )

        db.execute(
            text("UPDATE crm_deals SET deleted_at = now() WHERE id = :d"), {"d": deal.id}
        )
        db.expire_all()

        despues = svc.pipeline(db, EMPRESA_A)
        total_despues = next(
            c["total_deals"] for c in despues["columnas"] if c["stage"].id == primera.id
        )
        assert total_despues == total_antes - 1


class TestCuandoLaColumnaPasaDelTope:
    """Las tres afirmaciones que solo se pueden hacer con mas tratos que el tope.

    Sin esto, sumar las tarjetas devueltas y sumar todo dan el mismo numero, y
    las pruebas no distinguen una cosa de la otra. Lo encontro el arnes de
    mutacion: cambiar el calculo a "suma lo visible" no rompia nada.

    El tope se baja en vez de crear cincuenta tratos: la afirmacion es sobre el
    comportamiento al pasarlo, no sobre el numero.
    """

    @pytest.fixture(autouse=True)
    def tope_de_dos(self, monkeypatch):
        monkeypatch.setattr(svc, "TOPE_POR_COLUMNA", 2)

    def test_el_monto_es_el_REAL_y_no_el_de_las_tarjetas_devueltas(
        self, db: Session
    ) -> None:
        """El numero que se cita en una reunion.

        Con el tope en 2 y tres tratos de un millon, sumar lo visible daria dos
        millones: un tercio menos que el pipeline real, **sin que nada lo diga**.
        """
        empresa = _empresa(db)
        for _ in range(3):
            _trato(db, empresa, "1000000")
        db.flush()

        datos = svc.pipeline(db, EMPRESA_A)
        primera = svc.primera_etapa(db, EMPRESA_A)
        columna = next(c for c in datos["columnas"] if c["stage"].id == primera.id)

        assert len(columna["deals"]) == 2, "el tope no se aplico"
        assert columna["total_deals"] >= 3
        assert _monto(columna) >= Decimal("3000000"), (
            "el monto se calculo sobre las tarjetas devueltas, no sobre todo"
        )

    def test_se_DICE_que_la_lista_vino_cortada(self, db: Session) -> None:
        """Truncar en silencio se lee como "esto es todo lo que hay"."""
        empresa = _empresa(db)
        for _ in range(3):
            _trato(db, empresa, "1")
        db.flush()

        assert svc.pipeline(db, EMPRESA_A)["truncado"] is True

    def test_sin_pasar_el_tope_NO_se_marca_cortado(self, db: Session, monkeypatch) -> None:
        """Y esto es lo que impide que `truncado` sea siempre `True`.

        Una bandera que nunca baja no informa nada: la pantalla mostraria el
        aviso de lista incompleta con dos tratos.

        **Antes esta prueba se saltaba sola** si la base ya tenia tratos, con la
        nota de que "el seed no deja tratos". En cuanto se sembraron datos de
        demostracion la condicion dejo de cumplirse y la prueba paso a saltarse
        **siempre**: la unica que evita que `truncado` sea constante quedo sin
        correr, y en verde. Ahora sube el tope en vez de exigir una base vacia,
        asi que la afirmacion no depende de lo que haya alrededor.
        """
        monkeypatch.setattr(svc, "TOPE_POR_COLUMNA", 1000)
        _trato(db, _empresa(db), "1")
        db.flush()

        assert svc.pipeline(db, EMPRESA_A)["truncado"] is False


class TestLasEtapasInactivas:
    def test_una_etapa_apagada_no_se_dibuja(self, db: Session) -> None:
        """`active` es como se saca una columna del kanban sin borrarla.

        Los tratos que pasaron por ella conservan su historia; lo que se quita
        es la columna. Si se siguiera dibujando, apagarla no serviria de nada.
        """
        antes = len(svc.etapas_de(db, EMPRESA_A))
        db.execute(
            text(
                "UPDATE crm_stages SET active = false WHERE id = "
                "(SELECT id FROM crm_stages WHERE tenant_id = :t AND kind = 'open' "
                " ORDER BY position LIMIT 1)"
            ),
            {"t": str(EMPRESA_A)},
        )
        db.expire_all()

        assert len(svc.etapas_de(db, EMPRESA_A)) == antes - 1
        assert all(e.active for e in svc.etapas_de(db, EMPRESA_A))


class TestLasActividades:
    def test_una_actividad_cuelga_de_EXACTAMENTE_uno(self) -> None:
        with pytest.raises(svc.PadreInvalido):
            svc.validar_padre_de_actividad(
                {"crm_company_id": None, "crm_contact_id": None, "crm_deal_id": None}
            )

    def test_dos_padres_tampoco(self) -> None:
        """La misma llamada saldria dos veces en la linea de tiempo."""
        with pytest.raises(svc.PadreInvalido):
            svc.validar_padre_de_actividad(
                {
                    "crm_company_id": uuid.uuid4(),
                    "crm_contact_id": None,
                    "crm_deal_id": uuid.uuid4(),
                }
            )

    def test_uno_solo_pasa(self) -> None:
        svc.validar_padre_de_actividad(
            {"crm_company_id": uuid.uuid4(), "crm_contact_id": None, "crm_deal_id": None}
        )

    def test_LA_BASE_lo_exige_tambien(self, db: Session) -> None:
        """Y no solo el servicio.

        Un `UPDATE` a mano tiene que respetarlo igual: una actividad sin padre
        no aparece en ninguna ficha, y con dos sale duplicada.
        """
        with pytest.raises(Exception) as exc:
            db.execute(
                text(
                    "INSERT INTO crm_activities (tenant_id, kind, subject) "
                    "VALUES (:t, 'note', 'sin padre')"
                ),
                {"t": str(EMPRESA_A)},
            )
            db.flush()
        assert "ck_crm_activities_un_solo_padre" in str(exc.value)
        db.rollback()

    def test_la_linea_de_tiempo_de_una_empresa_incluye_la_de_sus_tratos(
        self, db: Session
    ) -> None:
        """Quien abre la ficha de un cliente quiere ver todo lo que paso con el,
        no la parte que alguien recordo anotar en el sitio exacto.
        """
        empresa = _empresa(db)
        deal = _trato(db, empresa)
        db.flush()

        db.execute(
            text(
                "INSERT INTO crm_activities (tenant_id, kind, subject, crm_deal_id) "
                "VALUES (:t, 'call', 'Llamada sobre el trato', :d)"
            ),
            {"t": str(EMPRESA_A), "d": deal.id},
        )
        db.flush()

        actividades = svc.linea_de_tiempo(db, EMPRESA_A, company_id=empresa.id)

        assert any(a.subject == "Llamada sobre el trato" for a in actividades), (
            "la actividad del trato no aparecio en la ficha de su empresa"
        )


class TestElAisladoEntreEmpresas:
    """#83 — lo que protege es RLS, no un `if`, y por eso va contra la base real."""

    def test_la_empresa_B_no_ve_lo_de_la_A(self, db: Session) -> None:
        _empresa(db, "Secreto comercial de A")
        db.flush()

        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"),
            {"t": "a0000000-0000-0000-0000-000000000002"},
        )
        db.expire_all()

        visibles = db.execute(text("SELECT count(*) FROM crm_companies")).scalar_one()
        assert visibles == 0, "la empresa B ve el CRM de la A"

    def test_la_empresa_B_no_puede_ESCRIBIR_en_la_carpeta_de_A(self, db: Session) -> None:
        """Y esto es lo que la politica `WITH CHECK` impide.

        Sin ella, RLS filtraria las lecturas y dejaria **insertar** filas con el
        `tenant_id` de otra empresa: invisibles para quien las escribio y
        visibles para la victima.
        """
        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"),
            {"t": "a0000000-0000-0000-0000-000000000002"},
        )
        with pytest.raises(Exception) as exc:
            db.execute(
                text("INSERT INTO crm_companies (tenant_id, name) VALUES (:t, 'intruso')"),
                {"t": str(EMPRESA_A)},
            )
            db.flush()
        assert "row-level security" in str(exc.value).lower()
        db.rollback()

    def test_las_cinco_tablas_tienen_RLS_forzada(self, db: Session) -> None:
        """`FORCE` importa: sin el, el dueno de la tabla se salta su propia
        politica, y una tarea que corra como dueno veria todas las empresas.
        """
        filas = db.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE relname LIKE 'crm_%' AND relkind = 'r' "
                "ORDER BY relname"
            )
        ).all()
        assert len(filas) == 5, f"faltan tablas del CRM: {[f[0] for f in filas]}"
        for nombre, activada, forzada in filas:
            assert activada, f"{nombre} sin RLS"
            assert forzada, f"{nombre} sin FORCE"
