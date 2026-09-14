"""El ciclo de vida de una declaracion y su urgencia (epica #21).

## Lo que estaba roto, medido con una sonda antes de tocar nada

`POST /obligations/{id}/fulfill` — el endpoint que registra el folio del portal
del Estado — **respondia 422 en el 100 % de los casos**:

    fulfill -> 422  {"detail":"Algun valor enviado no esta entre los
                     permitidos. (restriccion: obligations_status_check)"}

`fulfill_obligation` escribia `status = "fulfilled"`, un valor que el CHECK de
`obligations` no admite. Es la misma clase de error que ya tuvo
`evaluate_article` con `'not_evaluated'`: una lista de estados escrita de
memoria en vez de leida del esquema. Nadie lo noto porque **ninguna prueba
llamaba al endpoint**.

## Y un agujero que ese arreglo dejaba a la vista

`PATCH /obligations/{id}` aceptaba `status`. Con eso abierto la maquina de
estados es decorativa: se podia poner `accepted` directo, **sin folio y sin
haber presentado nada**, y la declaracion quedaba aceptada en pantalla sin
comprobante que mostrarle a un fiscalizador.

Las pruebas de `TestElFlujoNoSeSaltea` son las que importan. Aprobar se ve
funcionando; impedir que alguien salte al final, no.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.obligations import Obligation
from app.services.declaracion import (
    DIAS_CRITICO,
    DIAS_PROXIMO,
    TRANSICIONES,
    ErrorDeDeclaracion,
    FaltaElFolio,
    TransicionInvalida,
    aprobar,
    enviar,
    rechazar,
    registrar_folio,
    urgencia,
)

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
AHORA = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


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


@pytest.fixture
def declaracion(db: Session):
    """Una declaracion en borrador. La transaccion se deshace al terminar."""
    oid = db.execute(
        text(
            "INSERT INTO obligations (tenant_id, code, title, status) "
            "VALUES (:t, :c, 'Declaracion de prueba', 'draft') RETURNING id"
        ),
        {"t": str(EMPRESA_A), "c": f"PRB-{uuid.uuid4().hex[:8].upper()}"},
    ).scalar_one()
    return db.get(Obligation, oid)


def _con_plazo(dias: float, estado: str = "open") -> Obligation:
    """Una obligacion en memoria que vence dentro de `dias`. No toca la base."""
    return Obligation(
        tenant_id=EMPRESA_A,
        code="X",
        title="X",
        status=estado,
        due_at=AHORA + timedelta(days=dias),
    )


class TestElFolioNoEsOpcional:
    """#114 — el comprobante del portal es la unica prueba de que se declaro."""

    def test_fulfill_ya_no_escribe_un_estado_que_la_base_rechaza(
        self, db, declaracion
    ) -> None:
        """**La regresion.** Antes esto reventaba contra el CHECK."""
        registrar_folio(db, obligacion=declaracion, folio="SIDREP-2026-99812")

        assert declaracion.external_receipt == "SIDREP-2026-99812"
        # El estado NO cambia: registrar el folio y aceptar son dos momentos.
        assert declaracion.status == "draft"

    def test_el_estado_sigue_siendo_uno_de_los_que_admite_la_base(
        self, db, declaracion
    ) -> None:
        """Lee el CHECK real en vez de confiar en una lista escrita a mano.

        Es la comprobacion que faltaba: `'fulfilled'` era plausible leyendo el
        codigo y la base lo rechazaba.
        """
        registrar_folio(db, obligacion=declaracion, folio="F-1")
        db.flush()

        permitidos = db.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'obligations_status_check'"
            )
        ).scalar_one()

        assert f"'{declaracion.status}'" in permitidos

    def test_un_folio_vacio_no_se_guarda(self, db, declaracion) -> None:
        with pytest.raises(ErrorDeDeclaracion):
            registrar_folio(db, obligacion=declaracion, folio="   ")

    def test_no_se_puede_aceptar_sin_folio(self, db, declaracion) -> None:
        """**El error mas caro de este dominio.**

        Una declaracion aceptada sin comprobante deja a la empresa creyendo que
        cumplio, y nadie lo descubre hasta la fiscalizacion.
        """
        enviar(db, obligacion=declaracion)

        with pytest.raises(FaltaElFolio):
            aprobar(db, obligacion=declaracion, folio=None)

        assert declaracion.status == "submitted", "quedo a medio mover"

    def test_el_folio_puede_venir_de_antes(self, db, declaracion) -> None:
        registrar_folio(db, obligacion=declaracion, folio="SIDREP-1")
        enviar(db, obligacion=declaracion)

        aprobar(db, obligacion=declaracion)

        assert declaracion.status == "accepted"


class TestElFlujoNoSeSaltea:
    """#115 — las transiciones que no estan declaradas, no existen."""

    def test_no_se_acepta_algo_que_nadie_presento(self, db, declaracion) -> None:
        with pytest.raises(TransicionInvalida):
            aprobar(db, obligacion=declaracion, folio="F-1")

    def test_no_se_rechaza_algo_que_nadie_presento(self, db, declaracion) -> None:
        with pytest.raises(TransicionInvalida):
            rechazar(db, obligacion=declaracion, motivo="no")

    def test_una_declaracion_cerrada_no_vuelve_atras(self, db, declaracion) -> None:
        """El historial de una declaracion cerrada no se reescribe.

        Para rectificar se abre una nueva — que es lo que hace el propio RETC, y
        por eso `declaration_submissions.status` tiene `rectified`.
        """
        assert TRANSICIONES["closed"] == set()

        declaracion.status = "closed"
        with pytest.raises(TransicionInvalida):
            enviar(db, obligacion=declaracion)

    def test_rechazada_se_puede_rehacer(self, db, declaracion) -> None:
        """Rechazar no es el final: la empresa corrige y vuelve a presentar."""
        enviar(db, obligacion=declaracion)
        rechazar(db, obligacion=declaracion, motivo="Falta el anexo 2")

        enviar(db, obligacion=declaracion)

        assert declaracion.status == "submitted"

    def test_el_motivo_del_rechazo_queda_guardado(self, db, declaracion) -> None:
        enviar(db, obligacion=declaracion)

        rechazar(db, obligacion=declaracion, motivo="Falta el anexo 2")

        assert declaracion.data["motivo_rechazo"] == "Falta el anexo 2"

    def test_no_se_rechaza_sin_decir_por_que(self, db, declaracion) -> None:
        """Mientras se adivina que corregir, el plazo sigue corriendo."""
        enviar(db, obligacion=declaracion)

        with pytest.raises(ErrorDeDeclaracion):
            rechazar(db, obligacion=declaracion, motivo="   ")

        assert declaracion.status == "submitted"

    def test_rechazar_no_pisa_lo_que_ya_habia_en_data(self, db, declaracion) -> None:
        """`data` es de la obligacion, no del rechazo."""
        declaracion.data = {"periodo_declarado": "2026S1"}
        enviar(db, obligacion=declaracion)

        rechazar(db, obligacion=declaracion, motivo="Falta el anexo 2")

        assert declaracion.data["periodo_declarado"] == "2026S1"


class TestElSemaforo:
    """#113 — la urgencia, ahora calculada en el servidor."""

    def test_los_cuatro_tramos(self) -> None:
        assert urgencia(_con_plazo(60), AHORA).nivel == "vigente"
        assert urgencia(_con_plazo(DIAS_PROXIMO), AHORA).nivel == "proxima"
        assert urgencia(_con_plazo(DIAS_CRITICO), AHORA).nivel == "critica"
        assert urgencia(_con_plazo(-1), AHORA).nivel == "vencida"

    def test_una_aceptada_con_plazo_vencido_NO_esta_vencida(self) -> None:
        """**El orden de las preguntas, y no es intercambiable.**

        Una declaracion aceptada la semana pasada, con vencimiento ayer, esta
        lista — no vencida. Mirar la fecha antes que el estado la pintaria de
        rojo para siempre.
        """
        assert urgencia(_con_plazo(-30, estado="accepted"), AHORA).nivel == "resuelta"
        assert urgencia(_con_plazo(-30, estado="closed"), AHORA).nivel == "resuelta"

    def test_sin_plazo_no_es_lo_mismo_que_ir_bien(self) -> None:
        """Pintar de verde una obligacion sin fecha diria que va bien.

        No se sabe: nadie le puso plazo. Son estados distintos y se ven
        distintos.
        """
        sin_fecha = Obligation(tenant_id=EMPRESA_A, code="X", title="X", status="open")

        u = urgencia(sin_fecha, AHORA)

        assert u.nivel == "sin_plazo"
        assert u.dias_restantes is None

    def test_la_vispera_todavia_queda_un_dia(self) -> None:
        """**Truncar hacia abajo diria "vence hoy" toda la vispera.**

        A las 23:00 del dia anterior quedan 0,04 dias. Redondeando hacia abajo
        sale 0 y quien lo lee cree que ya no alcanza; hacia arriba sale 1, que
        es la verdad: manana vence.
        """
        vispera = Obligation(
            tenant_id=EMPRESA_A, code="X", title="X", status="open",
            due_at=AHORA + timedelta(hours=1),
        )

        assert urgencia(vispera, AHORA).dias_restantes == 1

    def test_los_dias_restantes_acompanan_al_nivel(self) -> None:
        u = urgencia(_con_plazo(7), AHORA)

        assert u.nivel == "proxima"
        assert u.dias_restantes == 7


# ── Por la API, que es por donde se usa ──────────────────────────────────

@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import SessionLocal
    from app.main import app

    monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)
    original = SessionLocal.kw.get("bind")
    motor = create_engine(URL)
    SessionLocal.configure(bind=motor)
    try:
        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original)
        motor.dispose()


@pytest.fixture
def limpiar():
    codigos: list[str] = []
    yield codigos
    admin = create_engine(
        os.getenv(
            "DATABASE_ADMIN_URL",
            "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
        )
    )
    try:
        with admin.begin() as c:
            for codigo in codigos:
                c.execute(text("DELETE FROM obligations WHERE code = :c"), {"c": codigo})
    finally:
        admin.dispose()


class TestPorLaApi:
    H = {"X-Tenant-Id": str(EMPRESA_A)}

    def _crear(self, cliente, limpiar, **extra) -> str:
        codigo = f"PRB-{uuid.uuid4().hex[:8].upper()}"
        limpiar.append(codigo)
        r = cliente.post(
            "/api/v1/obligations/",
            headers=self.H,
            json={"code": codigo, "title": "Declaracion", **extra},
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def test_el_flujo_entero(self, cliente, limpiar) -> None:
        oid = self._crear(cliente, limpiar)

        assert cliente.post(f"/api/v1/obligations/{oid}/submit", headers=self.H).status_code == 200
        assert cliente.post(
            f"/api/v1/obligations/{oid}/fulfill", headers=self.H, json={"folio": "SIDREP-1"}
        ).status_code == 200
        aceptada = cliente.post(
            f"/api/v1/obligations/{oid}/approve", headers=self.H, json={}
        )

        assert aceptada.status_code == 200, aceptada.text
        assert aceptada.json()["status"] == "accepted"
        assert aceptada.json()["external_receipt"] == "SIDREP-1"

    def test_fulfill_responde_200_y_no_422(self, cliente, limpiar) -> None:
        """**La regresion exacta que se midio.** Antes: 422, siempre."""
        oid = self._crear(cliente, limpiar)

        r = cliente.post(
            f"/api/v1/obligations/{oid}/fulfill", headers=self.H, json={"folio": "F-1"}
        )

        assert r.status_code == 200, r.text

    def test_el_patch_no_puede_mover_el_estado(self, cliente, limpiar) -> None:
        """**Sin esto la maquina de estados es decorativa.**

        Un PATCH a `accepted` saltaba el flujo entero: sin presentar y sin
        folio.
        """
        oid = self._crear(cliente, limpiar)

        r = cliente.patch(
            f"/api/v1/obligations/{oid}", headers=self.H, json={"status": "accepted"}
        )

        assert r.status_code == 409, r.text
        assert cliente.get(f"/api/v1/obligations/{oid}", headers=self.H).json()["status"] == "draft"

    def test_el_patch_normal_sigue_funcionando(self, cliente, limpiar) -> None:
        """La guarda no puede volverse un estorbo: editar el titulo es legitimo."""
        oid = self._crear(cliente, limpiar)

        r = cliente.patch(f"/api/v1/obligations/{oid}", headers=self.H, json={"title": "Otro"})

        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Otro"

    def test_mandar_el_mismo_estado_que_ya_tiene_no_molesta(self, cliente, limpiar) -> None:
        """Un formulario que reenvia el objeto entero no debe chocar contra la guarda."""
        oid = self._crear(cliente, limpiar)

        r = cliente.patch(
            f"/api/v1/obligations/{oid}", headers=self.H, json={"status": "draft", "title": "Otro"}
        )

        assert r.status_code == 200, r.text

    def test_el_listado_trae_el_semaforo(self, cliente, limpiar) -> None:
        """#113 — el criterio deja de vivir solo en el navegador."""
        self._crear(cliente, limpiar)

        filas = cliente.get("/api/v1/obligations/", headers=self.H).json()

        assert filas, "el listado vino vacio"
        assert all("urgencia" in f and "dias_restantes" in f for f in filas)

    def test_la_declaracion_dice_ante_que_portal_se_presenta(
        self, cliente, limpiar
    ) -> None:
        """#114 — antes el sistema se deducia partiendo el codigo por guiones."""
        oid = self._crear(cliente, limpiar, retc_system_id=11)

        assert cliente.get(f"/api/v1/obligations/{oid}", headers=self.H).json()[
            "retc_system_id"
        ] == 11

    def test_una_subtarea_de_otra_obligacion_se_rechaza(self, cliente, limpiar) -> None:
        """El arbol quedaria cruzado entre dos megaproyectos (#111).

        Y `parent_task_id` es una clave foranea, asi que **no pasa por RLS**:
        sin esta guarda podia colgar de la tarea de otra empresa.
        """
        a = self._crear(cliente, limpiar)
        b = self._crear(cliente, limpiar)
        tarea_de_a = cliente.post(
            f"/api/v1/obligations/{a}/tasks", headers=self.H, json={"title": "T1"}
        ).json()["id"]

        r = cliente.post(
            f"/api/v1/obligations/{b}/tasks",
            headers=self.H,
            json={"title": "T2", "parent_task_id": tarea_de_a},
        )

        assert r.status_code == 422, r.text

    def test_una_subtarea_de_la_misma_obligacion_se_acepta(
        self, cliente, limpiar
    ) -> None:
        """La guarda no puede impedir el caso que RF-26 pide: tareas y subtareas."""
        oid = self._crear(cliente, limpiar)
        padre = cliente.post(
            f"/api/v1/obligations/{oid}/tasks", headers=self.H, json={"title": "T1"}
        ).json()["id"]

        r = cliente.post(
            f"/api/v1/obligations/{oid}/tasks",
            headers=self.H,
            json={"title": "T1.1", "parent_task_id": padre},
        )

        assert r.status_code == 201, r.text
        assert r.json()["parent_task_id"] == padre



def _avisos_de(db, obligacion_id) -> list[dict]:
    """Los contextos de los avisos de una obligacion, leidos de la base.

    El generador nuevo devuelve conteos, no las filas: mantener una lista de
    objetos ORM invitaba a afirmar sobre lo que quedo en memoria en vez de sobre
    lo que se escribio, que no es lo mismo cuando hay un `flush` de por medio.
    """
    filas = db.execute(
        text(
            "SELECT context FROM notifications "
            "WHERE context->>'obligation_id' = :o AND deleted_at IS NULL"
        ),
        {"o": str(obligacion_id)},
    ).scalars().all()
    return list(filas)


def _en_dias_de_calendario(dias: int):
    """Un instante que cae `dias` dias mas adelante **en el calendario chileno**.

    Se fija a mediodia local a proposito: lejos de las dos medianoches, asi que
    ni el huso ni un cambio de hora pueden moverlo de dia.
    """
    from datetime import time
    from zoneinfo import ZoneInfo

    chile = ZoneInfo("America/Santiago")
    dia = (datetime.now(chile) + timedelta(days=dias)).date()
    return datetime.combine(dia, time(12, 0), tzinfo=chile)


class TestElRecordatorioLlevaSuPlantilla:
    """#117 — el aviso de vencimiento adjunta la plantilla del sistema.

    **El repositorio de plantillas esta vacio** (`declaration_templates` tiene
    cero filas): las plantillas Excel oficiales son contenido que hay que cargar
    desde los portales del Estado, no codigo que falte. Inventar una estructura
    de pestanas produciria declaraciones en un formato que el portal rechaza, y
    la empresa no lo sabria hasta que se la devuelven.

    Por eso estas pruebas **crean su propia plantilla**: verifican el mecanismo
    sin fingir que el repositorio existe.
    """

    def _plantilla(self, db, codigo_sistema: str, **extra) -> uuid.UUID:
        pais = db.execute(text("SELECT id FROM countries WHERE name = 'Chile'")).scalar_one()
        campos = {
            "valid_from": None,
            "valid_to": None,
            "active": True,
            **extra,
        }
        return db.execute(
            text(
                "INSERT INTO declaration_templates "
                "(country_id, system_code, name, version, valid_from, valid_to, active) "
                "VALUES (:p, :s, 'Plantilla de prueba', :v, :df, :dt, :a) RETURNING id"
            ),
            {
                "p": pais,
                "s": codigo_sistema,
                "v": f"v{uuid.uuid4().hex[:6]}",
                "df": campos["valid_from"],
                "dt": campos["valid_to"],
                "a": campos["active"],
            },
        ).scalar_one()

    def _sistema(self, db) -> tuple[int, str]:
        fila = db.execute(
            text("SELECT id, code FROM retc_systems WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
        ).first()
        if fila is None:  # pragma: no cover - catalogo vacio
            pytest.skip("No hay sistemas RETC sembrados.")
        return fila[0], fila[1]

    def test_adjunta_la_plantilla_del_sistema(self, db, declaracion) -> None:
        from app.services.avisos_de_vencimiento import _plantilla_de

        sistema_id, codigo = self._sistema(db)
        pid = self._plantilla(db, codigo)
        declaracion.retc_system_id = sistema_id
        db.flush()

        assert _plantilla_de(db, declaracion).id == pid

    def test_sin_sistema_no_hay_plantilla_que_adjuntar(self, db, declaracion) -> None:
        """Una obligacion que no se declara ante ningun portal es legitima."""
        from app.services.avisos_de_vencimiento import _plantilla_de

        assert declaracion.retc_system_id is None
        assert _plantilla_de(db, declaracion) is None

    def test_una_plantilla_caducada_NO_se_adjunta(self, db, declaracion) -> None:
        """**La comprobacion que importa de verdad.**

        Una plantilla marcada activa cuyo `valid_to` ya paso corresponde a una
        estructura que el portal dejo de aceptar. Adjuntarla haria que la
        empresa preparara su declaracion en un formato que le van a rechazar —
        y se entera cuando ya no hay plazo.
        """
        from datetime import date as _date

        from app.services.avisos_de_vencimiento import _plantilla_de

        sistema_id, codigo = self._sistema(db)
        self._plantilla(db, codigo, valid_to=_date(2020, 1, 1))
        declaracion.retc_system_id = sistema_id
        db.flush()

        assert _plantilla_de(db, declaracion) is None

    def test_una_plantilla_inactiva_tampoco(self, db, declaracion) -> None:
        from app.services.avisos_de_vencimiento import _plantilla_de

        sistema_id, codigo = self._sistema(db)
        self._plantilla(db, codigo, active=False)
        declaracion.retc_system_id = sistema_id
        db.flush()

        assert _plantilla_de(db, declaracion) is None

    def test_el_aviso_sale_igual_sin_plantilla(self, db, declaracion) -> None:
        """Un recordatorio sin adjunto sirve; uno que no se envia, no."""
        from app.services.avisos_de_vencimiento import generar

        persona = db.execute(
            text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
        ).scalar_one()
        declaracion.status = "open"
        declaracion.owner_user_id = persona
        # **Siete dias de CALENDARIO, no 7x24 horas.**
        #
        # `datetime.now(utc) + timedelta(days=7)` suma 168 horas, y eso no es
        # "dentro de siete dias" cuando hay un cambio de hora en el medio: Chile
        # pasa a horario de verano el primer sabado de septiembre, asi que a
        # comienzos de mes 168 horas caen en el **dia siguiente** al que una
        # persona llamaria "en una semana". Estas dos pruebas fallaron por eso, y
        # el mensaje —"no se genero el aviso"— acusaba al generador.
        #
        # El generador tiene razon: compara fechas del calendario en el huso de
        # la empresa, que es lo que significa "avisar 7 dias antes". La prueba
        # ahora habla el mismo idioma.
        declaracion.due_at = _en_dias_de_calendario(7)
        db.flush()

        generar(db, EMPRESA_A, ventanas=(7,))

        mios = _avisos_de(db, declaracion.id)
        assert mios, "no se genero el aviso"
        assert "template_id" not in mios[0]
        # Y de paso lleva la urgencia, que es lo que decide como se escribe.
        assert mios[0]["urgencia"] == "proxima"

    def test_con_plantilla_el_aviso_la_lleva(self, db, declaracion) -> None:
        from app.services.avisos_de_vencimiento import generar

        sistema_id, codigo = self._sistema(db)
        pid = self._plantilla(db, codigo)
        persona = db.execute(
            text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
        ).scalar_one()
        declaracion.status = "open"
        declaracion.owner_user_id = persona
        declaracion.retc_system_id = sistema_id
        # **Siete dias de CALENDARIO, no 7x24 horas.**
        #
        # `datetime.now(utc) + timedelta(days=7)` suma 168 horas, y eso no es
        # "dentro de siete dias" cuando hay un cambio de hora en el medio: Chile
        # pasa a horario de verano el primer sabado de septiembre, asi que a
        # comienzos de mes 168 horas caen en el **dia siguiente** al que una
        # persona llamaria "en una semana". Estas dos pruebas fallaron por eso, y
        # el mensaje —"no se genero el aviso"— acusaba al generador.
        #
        # El generador tiene razon: compara fechas del calendario en el huso de
        # la empresa, que es lo que significa "avisar 7 dias antes". La prueba
        # ahora habla el mismo idioma.
        declaracion.due_at = _en_dias_de_calendario(7)
        db.flush()

        generar(db, EMPRESA_A, ventanas=(7,))

        mios = _avisos_de(db, declaracion.id)
        assert mios, "no se genero el aviso"
        assert mios[0]["template_id"] == str(pid)
