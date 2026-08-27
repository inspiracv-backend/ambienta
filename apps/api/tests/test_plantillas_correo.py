"""El relleno de plantillas de notificacion (#121).

La prueba que manda es `TestNoEsUnMotorDePlantillas`: **las plantillas son dato
de empresa**, editable por un Admin Empresa desde una tabla con RLS. Si esto
usara Jinja2 o cualquier motor con expresiones, editar una plantilla seria
ejecutar codigo dentro del proceso de la API. Se llama SSTI y es de lo primero
que se prueba en un sistema que deja editar plantillas.

El resto comprueba lo aburrido: que una variable que falta no produzca un correo
con huecos ni tumbe el aviso.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.plantillas_correo import (
    aplicar,
    buscar,
    rellenar,
    variables_de,
)

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

#: La dueña de la base: **sin RLS**. Solo la usa `TestSinRLSElFiltroImporta`.
URL_DUENA = os.getenv(
    "DATABASE_ADMIN_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
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
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


class TestNoEsUnMotorDePlantillas:
    """Lo unico que hace es sustituir. Nada mas.

    Que estas pruebas pasen es lo que permite que un Admin Empresa edite sus
    propias plantillas sin que eso sea una via de ejecucion de codigo.
    """

    def test_no_evalua_expresiones(self) -> None:
        """La primera linea de la cadena conocida que termina en RCE."""
        ataque = "{{ ''.__class__.__mro__[1].__subclasses__() }}"
        salida, faltan = rellenar(ataque, {})
        assert salida == ataque, "se evaluo algo; esto tiene que quedar como texto"
        assert faltan == [], "ni siquiera lo reconoce como variable"

    def test_no_lee_atributos(self) -> None:
        class ConSecreto:
            secreto = "no deberia salir"

        salida, _ = rellenar("{{ objeto.secreto }}", {"objeto": ConSecreto()})
        assert "no deberia salir" not in salida

    def test_no_llama_funciones(self) -> None:
        llamadas = []

        def peligrosa():
            llamadas.append(1)
            return "ejecutada"

        salida, _ = rellenar("{{ funcion() }}", {"funcion": peligrosa})
        assert llamadas == [], "se ejecuto una funcion desde la plantilla"
        assert "ejecutada" not in salida

    def test_un_nombre_con_espacios_no_es_una_variable(self) -> None:
        """`{{ algo raro }}` no se reconoce, y eso es deliberado.

        Sin acotar el nombre a un identificador, cualquier cosa entre llaves
        seria una "variable" y los errores de tipeo se volverian marcadores
        mudos que nadie encuentra.
        """
        texto = "{{ dos palabras }}"
        salida, faltan = rellenar(texto, {"dos palabras": "valor"})
        assert salida == texto
        assert faltan == []


class TestLaSustitucion:
    def test_reemplaza_con_y_sin_espacios(self) -> None:
        salida, faltan = rellenar(
            "Hola {{nombre}}, vence el {{ fecha }}.",
            {"nombre": "Ana", "fecha": "01/09/2026"},
        )
        assert salida == "Hola Ana, vence el 01/09/2026."
        assert faltan == []

    def test_la_misma_variable_dos_veces(self) -> None:
        salida, _ = rellenar("{{x}} y {{x}}", {"x": "A"})
        assert salida == "A y A"

    def test_convierte_numeros(self) -> None:
        salida, _ = rellenar("faltan {{dias}} dias", {"dias": 7})
        assert salida == "faltan 7 dias"

    def test_una_variable_que_falta_deja_el_marcador_visible(self) -> None:
        """Las dos alternativas son peores.

        Reemplazar por vacio produce "La obligacion  vence el ", que se manda
        igual y llega asi al cliente. Reventar deja el aviso sin salir por un
        dato cosmetico.
        """
        salida, faltan = rellenar("Falta {{esto}} y {{aquello}}", {"esto": "A"})
        assert salida == "Falta A y {{aquello}}"
        assert faltan == ["aquello"], "y ademas se dice cual, sin leer el correo"

    def test_un_valor_nulo_cuenta_como_faltante(self) -> None:
        """`None` escrito en el correo sale como la palabra "None"."""
        salida, faltan = rellenar("Planta: {{planta}}", {"planta": None})
        assert "None" not in salida
        assert faltan == ["planta"]

    def test_texto_vacio_no_revienta(self) -> None:
        assert rellenar("", {}) == ("", [])
        assert rellenar(None, {}) == ("", [])


class TestElEscape:
    def test_escapa_html_cuando_se_pide(self) -> None:
        salida, _ = rellenar(
            "{{titulo}}", {"titulo": "<script>alert(1)</script>"}, escapar_html=True
        )
        assert "<script>" not in salida
        assert "&lt;script&gt;" in salida

    def test_no_escapa_cuando_es_texto_plano(self) -> None:
        """Un correo de texto con `&amp;` en vez de `&` se ve mal."""
        salida, _ = rellenar("{{t}}", {"t": "Aguas & Riles"}, escapar_html=False)
        assert salida == "Aguas & Riles"


class TestQueVariablesPide:
    def test_las_encuentra_sin_repetir(self) -> None:
        assert variables_de("a {{uno}} b {{dos}} c {{uno}}") == {"uno", "dos"}

    def test_sin_marcadores_devuelve_vacio(self) -> None:
        assert variables_de("texto sin nada") == set()


class TestBuscarEnLaBase:
    def test_encuentra_la_plantilla_sembrada(self, db: Session) -> None:
        p = buscar(
            db, tenant_id=EMPRESA_A, event_type="obligation_due", channel="email"
        )
        assert p is not None, (
            "no hay plantilla de vencimiento. Si esto falla, revisar que "
            "`db/20_plantillas_de_correo.sql` se haya aplicado."
        )
        assert p.channel == "email"
        assert p.active

    def test_un_evento_que_no_existe_devuelve_None(self, db: Session) -> None:
        assert (
            buscar(db, tenant_id=EMPRESA_A, event_type="inventado", channel="email")
            is None
        )

    def test_una_plantilla_inactiva_no_se_usa(self, db: Session) -> None:
        db.execute(
            text(
                "UPDATE notification_templates SET active = false "
                "WHERE event_type = 'obligation_due' AND channel = 'email' "
                "AND tenant_id = :t"
            ),
            {"t": str(EMPRESA_A)},
        )
        db.expire_all()
        assert (
            buscar(db, tenant_id=EMPRESA_A, event_type="obligation_due", channel="email")
            is None
        ), "una plantilla apagada se apago por algo"

    def test_el_canal_importa(self, db: Session) -> None:
        """La de correo no sirve para in-app: son textos distintos a proposito."""
        correo = buscar(
            db, tenant_id=EMPRESA_A, event_type="obligation_due", channel="email"
        )
        in_app = buscar(
            db, tenant_id=EMPRESA_A, event_type="obligation_due", channel="in_app"
        )
        assert correo is not None
        assert in_app is None or in_app.id != correo.id


class TestAplicar:
    def test_rellena_asunto_y_cuerpo_y_dice_que_falto(self, db: Session) -> None:
        p = buscar(
            db, tenant_id=EMPRESA_A, event_type="obligation_due", channel="email"
        )
        assert p is not None

        completo = {
            "obligation_code": "OBL-1",
            "obligation_title": "Declaracion de residuos",
            "days_remaining": 7,
            "due_date": "03/09/2026",
            "facility_name": "Planta Calama",
        }
        r = aplicar(p, completo)
        assert r.faltantes == [], f"la plantilla sembrada pide {r.faltantes}"
        assert "OBL-1" in r.asunto
        assert "Planta Calama" in r.cuerpo
        assert "{{" not in r.asunto + r.cuerpo, "quedo un marcador sin rellenar"

    def test_avisa_de_lo_que_falta_en_vez_de_reventar(self, db: Session) -> None:
        p = buscar(
            db, tenant_id=EMPRESA_A, event_type="obligation_due", channel="email"
        )
        assert p is not None
        r = aplicar(p, {"obligation_code": "OBL-1"})
        assert "facility_name" in r.faltantes
        assert r.asunto, "el asunto sale igual, con el marcador a la vista"

    def test_delata_una_plantilla_que_se_quedo_vieja(self, db: Session) -> None:
        """`sin_usar` no es un error: el contexto es el mismo para todas.

        Pero si alguien agrega un dato al aviso y ninguna plantilla lo usa, esto
        lo dice sin tener que leer las plantillas una por una.
        """
        p = buscar(
            db, tenant_id=EMPRESA_A, event_type="obligation_due", channel="email"
        )
        assert p is not None
        r = aplicar(p, {"un_dato_nuevo": "x"})
        assert "un_dato_nuevo" in r.sin_usar


class TestSinRLSElFiltroImporta:
    """Por que `buscar()` filtra por empresa aunque RLS ya lo haga.

    El arnes de mutacion encontro esto: quitar
    `NotificationTemplate.tenant_id == tenant_id` **no rompia ninguna prueba**,
    porque todas corren con el contexto de RLS declarado y Postgres ya filtraba.
    O sea que la linea parecia redundante y nada habria avisado si alguien la
    borraba "porque RLS ya se encarga".

    No es redundante: `buscar()` recibe una sesion cualquiera, y una sesion de
    dueño de la base —como la que usa el despachador— no tiene RLS. Esta prueba
    corre justamente asi, que es la unica forma de que el filtro signifique
    algo.
    """

    @pytest.fixture
    def db_sin_rls(self):
        engine = create_engine(URL_DUENA)
        try:
            conexion = engine.connect()
        except Exception as exc:  # pragma: no cover - entorno sin base
            pytest.skip(f"Sin base de datos disponible: {exc}")
        s = Session(bind=conexion)
        try:
            yield s
        finally:
            s.rollback()
            s.close()
            conexion.close()
            engine.dispose()

    def test_no_devuelve_la_plantilla_de_otra_empresa(self, db_sin_rls: Session) -> None:
        otra = db_sin_rls.execute(
            text("SELECT id FROM tenants WHERE id <> :a AND deleted_at IS NULL LIMIT 1"),
            {"a": str(EMPRESA_A)},
        ).scalar()
        if otra is None:
            pytest.skip("El seed tiene una sola empresa; no se puede cruzar nada")

        # Se comprueba primero que la otra empresa TIENE una: si no, esta
        # prueba pasaria por no haber nada que devolver, no por el filtro.
        de_la_otra = buscar(
            db_sin_rls, tenant_id=otra, event_type="obligation_due", channel="email"
        )
        assert de_la_otra is not None, (
            "la otra empresa no tiene plantilla, asi que esto no probaria nada. "
            "Revisar que `db/20_plantillas_de_correo.sql` se haya aplicado."
        )

        de_la_nuestra = buscar(
            db_sin_rls, tenant_id=EMPRESA_A, event_type="obligation_due", channel="email"
        )
        assert de_la_nuestra is not None
        assert de_la_nuestra.id != de_la_otra.id
        assert de_la_nuestra.tenant_id == EMPRESA_A, (
            "sin RLS, el filtro explicito es lo unico que separa las plantillas "
            "de una empresa de las de otra"
        )
