"""Los avisos de vencimiento: cuando, a quien, y una sola vez (epica #22).

## Los tres defectos que tenia el generador anterior, medidos con sondas

**1. Duplicaba (#119).** Tres corridas seguidas sobre la misma obligacion y la
misma ventana dejaban tres avisos:

    1a corrida: 1 aviso
    2a corrida: 1 aviso
    3a corrida: 1 aviso
    avisos para LA MISMA obligacion: 3

El generador esta pensado para un cron diario. Un reinicio, un reintento o dos
trabajadores, y la persona recibe el mismo correo repetido. **El dano no es el
ruido sino lo que provoca:** un sistema que avisa de mas se deja de leer, y
despues pasa de largo el aviso que importaba.

**2. Las obligaciones sin responsable no avisaban a nadie (#123).**

    if not obl.owner_user_id:
        continue

En el seed son **3 de 8**. Las mas expuestas —nadie se hizo cargo— eran justo
las que no generaban ningun aviso, en silencio.

**3. Las ventanas escritas a mano (#120).** `[30, 15, 7, 1]` en el codigo,
mientras `notification_rules` con `lead_minutes` por empresa existia con **cero
filas** y nadie la leia.

## Lo que se prueba y lo que no

Las pruebas de duplicacion y escalamiento van **contra la base real**: lo que
protege del duplicado es una restriccion de unicidad (`db/17`), no un `if`, y
eso no se puede comprobar con una sesion simulada.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.obligations import Obligation
from app.services.avisos_de_vencimiento import (
    EVENTO,
    VENTANAS_POR_DEFECTO,
    generar,
    ventanas_de,
)

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
        # Todo se deshace: estas pruebas escriben en `obligations`,
        # `notifications` y `notification_rules`, que son tablas vivas.
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


def _obligacion(db: Session, *, dias: int, con_responsable: bool) -> Obligation:
    persona = None
    if con_responsable:
        persona = db.execute(
            text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
        ).scalar_one()

    oid = db.execute(
        text(
            "INSERT INTO obligations (tenant_id, code, title, status, due_at, owner_user_id) "
            "VALUES (:t, :c, :ti, 'open', now() + make_interval(days => :d), :u) "
            "RETURNING id"
        ),
        {
            "t": str(EMPRESA_A),
            "c": f"PRB-{uuid.uuid4().hex[:8].upper()}",
            "ti": "Con responsable" if con_responsable else "SIN responsable",
            "d": dias,
            "u": persona,
        },
    ).scalar_one()
    db.flush()
    return db.get(Obligation, oid)


#: Los canales que genera un aviso de vencimiento (RF-32). Hasta el 27-ago solo
#: se creaba el in-app, asi que **la tuberia de correo no tenia nada que
#: enviar**: se podia configurar Resend entero y no salia un solo mensaje.
CANALES = ("in_app", "email")


def _avisos_de(db: Session, obligacion_id, canal: str = "in_app") -> int:
    """Avisos de una obligacion **en un canal**.

    Cuenta por canal y no en total a proposito. Contar el total hace que
    "un aviso por obligacion" y "dos canales del mismo aviso" den el mismo
    numero, y entonces la prueba de duplicados no distingue el caso que le
    importa —el cron corrio dos veces— del que es correcto.
    """
    return db.execute(
        text(
            "SELECT count(*) FROM notifications "
            "WHERE context->>'obligation_id' = :o AND channel = :c "
            "AND deleted_at IS NULL"
        ),
        {"o": str(obligacion_id), "c": canal},
    ).scalar_one()


def _avisos_totales(db: Session, obligacion_id) -> int:
    return sum(_avisos_de(db, obligacion_id, c) for c in CANALES)


class TestNoDuplica:
    """#119 — el cron corre todos los dias y no puede repetir lo de ayer."""

    def test_dos_corridas_no_dan_dos_avisos(self, db) -> None:
        """**La regresion exacta que se midio.** Antes: 3 corridas, 3 avisos."""
        obl = _obligacion(db, dias=7, con_responsable=True)

        generar(db, EMPRESA_A, ventanas=(7,))
        generar(db, EMPRESA_A, ventanas=(7,))
        generar(db, EMPRESA_A, ventanas=(7,))

        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 1, canal

    def test_la_segunda_corrida_lo_informa_en_vez_de_callarlo(self, db) -> None:
        """No repetir **es lo esperado**, no un error, y por eso se cuenta aparte.

        Un `created: 0` a secas se lee como "algo fallo".
        """
        _obligacion(db, dias=7, con_responsable=True)
        generar(db, EMPRESA_A, ventanas=(7,))

        r = generar(db, EMPRESA_A, ventanas=(7,))

        assert r.creados == 0
        assert r.omitidos_por_repetidos >= 1

    def test_una_obligacion_en_dos_ventanas_no_se_duplica_en_la_misma_corrida(
        self, db
    ) -> None:
        """**El caso que el `flush` por obligacion protege.**

        Con el margen de 12 horas, dos ventanas contiguas pueden atrapar la
        misma obligacion. Sin el `flush`, la comprobacion no ve lo insertado
        hace un instante y la duplica dentro de la misma corrida.
        """
        obl = _obligacion(db, dias=7, con_responsable=True)

        generar(db, EMPRESA_A, ventanas=(7, 7))

        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 1, canal

    def test_ventanas_distintas_SI_dan_avisos_distintos(self, db) -> None:
        """El otro lado: no duplicar no puede volverse no avisar.

        A 15 dias y a 7 son dos avisos legitimos de la misma obligacion.
        """
        obl = _obligacion(db, dias=7, con_responsable=True)
        generar(db, EMPRESA_A, ventanas=(7,))

        # Se mueve el vencimiento para que caiga en la otra ventana.
        db.execute(
            text("UPDATE obligations SET due_at = now() + interval '15 days' WHERE id = :i"),
            {"i": obl.id},
        )
        generar(db, EMPRESA_A, ventanas=(15,))

        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 2, canal


class TestSinResponsableEscala:
    """#123 — la obligacion sin dueno es mas urgente, no menos."""

    def test_una_obligacion_sin_responsable_SI_genera_avisos(self, db) -> None:
        """**Antes generaba cero, en silencio.** En el seed son 3 de 8."""
        obl = _obligacion(db, dias=7, con_responsable=False)

        r = generar(db, EMPRESA_A, ventanas=(7,))

        assert _avisos_totales(db, obl.id) > 0
        assert r.escalados == 1

    def test_el_aviso_escalado_dice_por_que_llego(self, db) -> None:
        """Un aviso sobre algo que la persona no reconoce como suyo se archiva.

        Tiene que explicar que llego por falta de responsable, y que hacer.
        """
        obl = _obligacion(db, dias=7, con_responsable=False)

        generar(db, EMPRESA_A, ventanas=(7,))

        cuerpo = db.execute(
            text(
                "SELECT body FROM notifications "
                "WHERE context->>'obligation_id' = :o LIMIT 1"
            ),
            {"o": str(obl.id)},
        ).scalar_one()
        assert "no tiene un responsable asignado" in cuerpo

    def test_el_contexto_marca_que_fue_escalado(self, db) -> None:
        """Para que la pantalla pueda distinguirlo sin leer el texto."""
        obl = _obligacion(db, dias=7, con_responsable=False)

        generar(db, EMPRESA_A, ventanas=(7,))

        escalado = db.execute(
            text(
                "SELECT context->>'escalado' FROM notifications "
                "WHERE context->>'obligation_id' = :o LIMIT 1"
            ),
            {"o": str(obl.id)},
        ).scalar_one()
        assert escalado == "true"

    def test_con_responsable_NO_escala(self, db) -> None:
        """Escalar siempre seria avisar a los administradores de todo."""
        obl = _obligacion(db, dias=7, con_responsable=True)

        r = generar(db, EMPRESA_A, ventanas=(7,))

        assert r.escalados == 0
        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 1, canal

    def test_un_escalamiento_a_medias_se_completa_en_la_corrida_siguiente(
        self, db
    ) -> None:
        """Si la base se cae entre dos administradores, el resto tiene que llegar.

        Por eso se pregunta **por destinatario** y no por clave a secas.
        """
        obl = _obligacion(db, dias=7, con_responsable=False)
        generar(db, EMPRESA_A, ventanas=(7,))
        total = _avisos_totales(db, obl.id)
        assert total >= 2, "hacen falta al menos dos administradores para esta prueba"

        # Se borra uno, como si nunca se hubiera escrito.
        db.execute(
            text(
                "DELETE FROM notifications WHERE id IN ("
                "  SELECT id FROM notifications "
                "  WHERE context->>'obligation_id' = :o LIMIT 1)"
            ),
            {"o": str(obl.id)},
        )

        generar(db, EMPRESA_A, ventanas=(7,))

        assert _avisos_totales(db, obl.id) == total, "no se completo el que faltaba"


class TestLasVentanas:
    """#120 — configurables por empresa, con un defecto que funciona solo."""

    def test_sin_reglas_usa_el_defecto(self, db) -> None:
        """Un tenant nuevo tiene que recibir avisos sin configurar nada."""
        assert ventanas_de(db, EMPRESA_A) == VENTANAS_POR_DEFECTO

    def test_el_defecto_es_el_del_requisito(self) -> None:
        """15/7/3/1 (#120), no los 30/15/7/1 que decia el codigo.

        Los 30 dias no estaban en ningun requisito: solo en esa linea.
        """
        assert VENTANAS_POR_DEFECTO == (15, 7, 3, 1)

    def test_una_regla_de_la_empresa_gana_sobre_el_defecto(self, db) -> None:
        db.execute(
            text(
                "INSERT INTO notification_rules "
                "(tenant_id, event_type, channel, lead_minutes, template_code) "
                "VALUES (:t, :e, 'in_app', :m, 'vencimiento')"
            ),
            {"t": str(EMPRESA_A), "e": EVENTO, "m": 10 * 1440},
        )
        db.flush()

        assert ventanas_de(db, EMPRESA_A) == (10,)

    def test_dos_reglas_con_el_mismo_plazo_no_avisan_dos_veces(self, db) -> None:
        """Es un error de configuracion, no una razon para duplicar."""
        for _ in range(2):
            db.execute(
                text(
                    "INSERT INTO notification_rules "
                    "(tenant_id, event_type, channel, lead_minutes, template_code) "
                    "VALUES (:t, :e, 'in_app', :m, 'vencimiento')"
                ),
                {"t": str(EMPRESA_A), "e": EVENTO, "m": 5 * 1440},
            )
        db.flush()

        assert ventanas_de(db, EMPRESA_A) == (5,)

    def test_una_regla_inactiva_no_cuenta(self, db) -> None:
        db.execute(
            text(
                "INSERT INTO notification_rules "
                "(tenant_id, event_type, channel, lead_minutes, template_code, active) "
                "VALUES (:t, :e, 'in_app', :m, 'vencimiento', false)"
            ),
            {"t": str(EMPRESA_A), "e": EVENTO, "m": 99 * 1440},
        )
        db.flush()

        assert ventanas_de(db, EMPRESA_A) == VENTANAS_POR_DEFECTO

    def test_un_aviso_posterior_al_vencimiento_no_se_mezcla(self, db) -> None:
        """`lead_minutes` negativo es "avisar despues", que el esquema contempla.

        Es otro caso de uso. Colarlo aca produciria una ventana negativa y
        avisos de vencimientos que ya pasaron mezclados con los que vienen.
        """
        db.execute(
            text(
                "INSERT INTO notification_rules "
                "(tenant_id, event_type, channel, lead_minutes, template_code) "
                "VALUES (:t, :e, 'in_app', :m, 'vencimiento')"
            ),
            {"t": str(EMPRESA_A), "e": EVENTO, "m": -3 * 1440},
        )
        db.flush()

        assert ventanas_de(db, EMPRESA_A) == VENTANAS_POR_DEFECTO


class TestQueNoSeAvisa:
    def test_una_declaracion_aceptada_no_genera_aviso(self, db) -> None:
        obl = _obligacion(db, dias=7, con_responsable=True)
        db.execute(
            text("UPDATE obligations SET status = 'accepted' WHERE id = :i"),
            {"i": obl.id},
        )

        generar(db, EMPRESA_A, ventanas=(7,))

        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 0, canal

    def test_una_presentada_SI_genera_aviso(self, db) -> None:
        """Se presento pero no la aceptaron: el plazo corre igual."""
        obl = _obligacion(db, dias=7, con_responsable=True)
        db.execute(
            text("UPDATE obligations SET status = 'submitted' WHERE id = :i"),
            {"i": obl.id},
        )

        generar(db, EMPRESA_A, ventanas=(7,))

        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 1, canal

    def test_una_que_vence_fuera_de_la_ventana_no_avisa(self, db) -> None:
        obl = _obligacion(db, dias=60, con_responsable=True)

        generar(db, EMPRESA_A, ventanas=(7,))

        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 0, canal

    def test_el_margen_atrapa_un_vencimiento_a_media_tarde(self, db) -> None:
        """**Sin margen no se avisaria nunca.**

        El cron corre a una hora fija y el vencimiento cae a cualquier hora: un
        vencimiento a las 09:00 jamas esta exactamente a N dias del momento de
        la corrida.
        """
        obl = _obligacion(db, dias=7, con_responsable=True)
        db.execute(
            text(
                "UPDATE obligations SET due_at = now() + interval '7 days' "
                "- interval '8 hours' WHERE id = :i"
            ),
            {"i": obl.id},
        )

        generar(db, EMPRESA_A, ventanas=(7,))

        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 1, canal


class TestLoQueNoAvisoANadie:
    def test_se_informa_en_vez_de_saltarse_en_silencio(self, db, monkeypatch) -> None:
        """**El numero que hay que mirar.**

        Una empresa sin responsable ni administrador activo no recibe nada, y
        eso tiene que verse en el resultado de la corrida — no descubrirse el
        dia que vence algo.
        """
        from app.services import avisos_de_vencimiento as svc

        obl = _obligacion(db, dias=7, con_responsable=False)
        monkeypatch.setattr(svc, "_destinatarios", lambda *_: ([], True))

        r = generar(db, EMPRESA_A, ventanas=(7,))

        assert obl.code in r.sin_destinatario
        for canal in CANALES:
            assert _avisos_de(db, obl.id, canal) == 0, canal


class TestPorLaApi:
    H = {"X-Tenant-Id": str(EMPRESA_A)}

    @pytest.fixture
    def cliente(self, monkeypatch):
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
    def obligacion_confirmada(self):
        """Una obligacion que vence en 7 dias, **confirmada en la base**.

        El endpoint corre en su propia sesion y hace `commit`, asi que no ve lo
        que escriba una transaccion que despues se deshace. Por eso esta se
        escribe con la conexion del dueno y se borra al terminar, junto con los
        avisos que haya generado.
        """
        admin = create_engine(
            os.getenv(
                "DATABASE_ADMIN_URL",
                "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
            )
        )
        codigo = f"APIPRB-{uuid.uuid4().hex[:8].upper()}"
        with admin.begin() as c:
            persona = c.execute(
                text("SELECT id FROM users WHERE tenant_id = :t AND deleted_at IS NULL LIMIT 1"),
                {"t": str(EMPRESA_A)},
            ).scalar_one()
            oid = c.execute(
                text(
                    "INSERT INTO obligations (tenant_id, code, title, status, due_at, owner_user_id) "
                    "VALUES (:t, :c, 'Prueba de la API', 'open', now() + interval '7 days', :u) "
                    "RETURNING id"
                ),
                {"t": str(EMPRESA_A), "c": codigo, "u": persona},
            ).scalar_one()

        yield oid

        with admin.begin() as c:
            c.execute(
                text("DELETE FROM notifications WHERE context->>'obligation_id' = :o"),
                {"o": str(oid)},
            )
            c.execute(text("DELETE FROM obligations WHERE code = :c"), {"c": codigo})
        admin.dispose()

    def test_el_endpoint_informa_lo_que_hizo_y_lo_que_no(self, cliente) -> None:
        """Un `{"created": N}` a secas no deja ver ni los repetidos ni los
        escalados ni —lo importante— los que no avisaron a nadie."""
        r = cliente.post("/api/v1/obligations/generate-notifications/", headers=self.H)

        assert r.status_code == 200, r.text
        cuerpo = r.json()
        for campo in (
            "created",
            "skipped_duplicates",
            "escalated",
            "without_recipient",
            "windows_days",
        ):
            assert campo in cuerpo, f"falta {campo}"

    def test_llamarlo_dos_veces_no_crea_nada_la_segunda(
        self, cliente, obligacion_confirmada
    ) -> None:
        """El cron con reintentos es el caso normal, no la excepcion.

        **La primera version de esta prueba era vacua.** Solo afirmaba que la
        segunda llamada creaba 0, y sobre el seed la primera tambien creaba 0
        —ninguna obligacion caia en una ventana— asi que pasaba sin comprobar
        nada. Medido:

            1a: {'created': 0, ...}
            2a: {'created': 0, ...}

        Ahora la prueba **crea su propia obligacion confirmada**, para que la
        primera llamada tenga algo que hacer, y afirma sobre las dos.
        """
        primera = cliente.post(
            "/api/v1/obligations/generate-notifications/", headers=self.H
        ).json()
        assert primera["created"] > 0, "la primera corrida no creo nada: prueba vacua"

        segunda = cliente.post(
            "/api/v1/obligations/generate-notifications/", headers=self.H
        ).json()

        assert segunda["created"] == 0
        assert segunda["skipped_duplicates"] > 0


class TestLosDosCanales:
    """RF-32: correo **y** in-app. Hasta el 27-ago solo se creaba el in-app.

    El efecto de esa falta era invisible mientras no hubiera proveedor de
    correo: se podia configurar Resend entero, correr el cron, y no salia un
    solo mensaje — porque nunca hubo una fila `channel = 'email'` que enviar.
    """

    def test_se_crean_los_dos(self, db) -> None:
        obl = _obligacion(db, dias=7, con_responsable=True)
        generar(db, EMPRESA_A, ventanas=(7,))
        db.flush()

        assert _avisos_de(db, obl.id, "in_app") == 1
        assert _avisos_de(db, obl.id, "email") == 1, (
            "sin esta fila la tuberia de correo no tiene nada que enviar"
        )

    def test_las_claves_se_distinguen_por_canal(self, db) -> None:
        """Sin el canal en la clave, la base rechaza el segundo.

        El indice unico es `(tenant, clave, destinatario)`: dos avisos de la
        misma obligacion y la misma ventana para la misma persona chocarian, y
        la persona recibiria uno de los dos en vez de los dos.
        """
        obl = _obligacion(db, dias=7, con_responsable=True)
        generar(db, EMPRESA_A, ventanas=(7,))
        db.flush()

        claves = db.execute(
            text(
                "SELECT channel, dedupe_key FROM notifications "
                "WHERE context->>'obligation_id' = :o"
            ),
            {"o": str(obl.id)},
        ).all()
        assert len({c for _, c in claves}) == len(claves), "dos canales, dos claves"
        for canal, clave in claves:
            assert clave.endswith(canal)

    def test_el_correo_usa_la_plantilla_de_la_empresa(self, db) -> None:
        """Lo que pedia #121, comprobado sobre el texto que sale."""
        obl = _obligacion(db, dias=7, con_responsable=True)
        generar(db, EMPRESA_A, ventanas=(7,))
        db.flush()

        asunto = db.execute(
            text(
                "SELECT subject FROM notifications "
                "WHERE context->>'obligation_id' = :o AND channel = 'email'"
            ),
            {"o": str(obl.id)},
        ).scalar_one()

        assert obl.code in asunto, "la plantilla pide {{obligation_code}}"
        assert "{{" not in asunto, "quedo un marcador sin rellenar"

    def test_sin_plantilla_el_correo_sale_igual(self, db) -> None:
        """Falla suave: un aviso sin diseno sirve, uno que no se envia no."""
        db.execute(
            text(
                "UPDATE notification_templates SET active = false "
                "WHERE event_type = 'obligation_due' AND tenant_id = :t"
            ),
            {"t": str(EMPRESA_A)},
        )
        db.expire_all()

        obl = _obligacion(db, dias=7, con_responsable=True)
        generar(db, EMPRESA_A, ventanas=(7,))
        db.flush()

        cuerpo = db.execute(
            text(
                "SELECT body FROM notifications "
                "WHERE context->>'obligation_id' = :o AND channel = 'email'"
            ),
            {"o": str(obl.id)},
        ).scalar_one()
        assert obl.title in cuerpo

    def test_el_contexto_trae_lo_que_la_plantilla_pide(self, db) -> None:
        """Si se agrega una variable a la plantilla y no al contexto, el
        marcador sale visible en un correo a un cliente. Esto lo fija.
        """
        obl = _obligacion(db, dias=7, con_responsable=True)
        generar(db, EMPRESA_A, ventanas=(7,))
        db.flush()

        contexto = db.execute(
            text(
                "SELECT context FROM notifications "
                "WHERE context->>'obligation_id' = :o AND channel = 'email'"
            ),
            {"o": str(obl.id)},
        ).scalar_one()

        for variable in (
            "obligation_code",
            "obligation_title",
            "days_remaining",
            "due_date",
            "facility_name",
        ):
            assert variable in contexto, f"la plantilla pide {variable} y no esta"

    def test_una_obligacion_sin_planta_no_deja_el_marcador_a_la_vista(self, db) -> None:
        """No todas tienen planta: un compromiso de RCA es de la empresa entera."""
        obl = _obligacion(db, dias=7, con_responsable=True)
        db.execute(
            text("UPDATE obligations SET facility_id = NULL WHERE id = :o"),
            {"o": obl.id},
        )
        db.expire_all()

        generar(db, EMPRESA_A, ventanas=(7,))
        db.flush()

        cuerpo = db.execute(
            text(
                "SELECT body FROM notifications "
                "WHERE context->>'obligation_id' = :o AND channel = 'email'"
            ),
            {"o": str(obl.id)},
        ).scalar_one()
        assert "{{facility_name}}" not in cuerpo
        assert "toda la empresa" in cuerpo
