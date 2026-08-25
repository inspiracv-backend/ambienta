"""Acceso temporal del Cliente Invitado (RF-01, RF-02, RF-07).

Cubre los **siete escenarios** del requisito, y **los tres de negacion son los
que importan**: emitir una credencial es facil de ver funcionando, negarla no.

Un fallo aca no se nota mirando la pantalla — el invitado entra igual, solo que
viendo algo que no le toca. Por eso las pruebas atacan los limites: credencial
inventada, vencida, revocada, y de otra empresa.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.rut import es_valido
from app.services.invitado import DIAS_DE_VIGENCIA, autenticar, emitir

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EMPRESA_B = uuid.UUID("a0000000-0000-0000-0000-000000000002")


def _sesion(engine, tenant_id: uuid.UUID) -> Session:
    """Una sesion con la empresa declarada, como la arma la API."""
    conexion = engine.connect()
    s = Session(bind=conexion)
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"),
        {"t": str(tenant_id)},
    )
    s.info["_conexion"] = conexion
    return s


@pytest.fixture
def engine():
    e = create_engine(URL)
    try:
        e.connect().close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    yield e
    e.dispose()


@pytest.fixture
def db(engine):
    s = _sesion(engine, EMPRESA_A)
    try:
        yield s
    finally:
        s.rollback()
        s.info["_conexion"].close()
        s.close()


class TestGenerarElAcceso:
    """Escenario: generar el acceso desde el link publico."""

    def test_entrega_un_rut_valido_y_una_clave(self, db: Session) -> None:
        c = emitir(db, EMPRESA_A)

        assert es_valido(c.rut), f"El RUT emitido no pasa su propia validacion: {c.rut}"
        assert len(c.clave) == 6

    def test_dice_hasta_cuando_sirve(self, db: Session) -> None:
        """El requisito lo pide explicito: la persona tiene que saber el plazo."""
        c = emitir(db, EMPRESA_A)

        esperado = datetime.now(timezone.utc) + timedelta(days=DIAS_DE_VIGENCIA)
        assert abs((c.valido_hasta - esperado).total_seconds()) < 60

    def test_la_clave_no_queda_en_claro_en_la_base(self, db: Session) -> None:
        """**La propiedad que no se ve mirando la pantalla.**

        El acceso es de bajo privilegio, pero la persona probablemente reuse esa
        clave en otro lado.
        """
        c = emitir(db, EMPRESA_A)
        db.flush()

        guardado = db.execute(
            text("SELECT password_hash FROM guest_credentials WHERE rut = :r"),
            {"r": c.rut},
        ).scalar_one()

        assert c.clave not in guardado
        assert len(guardado) == 64  # sha256 en hexadecimal

    def test_el_rut_emitido_no_choca_con_el_de_una_persona_real(
        self, db: Session
    ) -> None:
        """Arranca en 90.000.000, por encima de los RUT de personas.

        Si colisionara, dos personas distintas competirian por la misma
        credencial dentro de la empresa.
        """
        for _ in range(5):
            c = emitir(db, EMPRESA_A)
            assert int(c.rut.split("-")[0]) >= 90_000_000

    def test_dos_emisiones_dan_credenciales_distintas(self, db: Session) -> None:
        a = emitir(db, EMPRESA_A)
        b = emitir(db, EMPRESA_A)

        assert a.rut != b.rut
        assert a.clave != b.clave


class TestVolverConCredencialesVigentes:
    """Escenario: volver con credenciales de una visita anterior."""

    def test_el_rut_y_la_clave_correctos_dejan_entrar(self, db: Session) -> None:
        c = emitir(db, EMPRESA_A)
        db.flush()

        quien = autenticar(db, EMPRESA_A, c.rut, c.clave)

        assert quien is not None
        assert quien.tenant_id == EMPRESA_A
        assert quien.rut == c.rut

    def test_los_tres_formatos_del_rut_sirven_para_entrar(self, db: Session) -> None:
        """La persona lo copia del correo o lo escribe de memoria, con puntos o
        sin ellos. Rechazarla por el formato seria negarle su propio acceso."""
        c = emitir(db, EMPRESA_A)
        db.flush()

        cuerpo, dv = c.rut.split("-")
        for variante in [c.rut, f"{cuerpo}{dv}", f"{cuerpo}-{dv.lower()}"]:
            assert autenticar(db, EMPRESA_A, variante, c.clave) is not None, variante

    def test_usar_la_credencial_no_le_estira_la_vigencia(self, db: Session) -> None:
        """**Una credencial que se renueva al usarla nunca caduca**, y entonces
        la vigencia no significa nada."""
        c = emitir(db, EMPRESA_A)
        db.flush()
        antes = db.execute(
            text("SELECT valid_until FROM guest_credentials WHERE rut = :r"),
            {"r": c.rut},
        ).scalar_one()

        autenticar(db, EMPRESA_A, c.rut, c.clave)

        despues = db.execute(
            text("SELECT valid_until FROM guest_credentials WHERE rut = :r"),
            {"r": c.rut},
        ).scalar_one()
        assert antes == despues

    def test_registra_el_uso(self, db: Session) -> None:
        c = emitir(db, EMPRESA_A)
        db.flush()

        autenticar(db, EMPRESA_A, c.rut, c.clave)

        usado = db.execute(
            text("SELECT last_used_at FROM guest_credentials WHERE rut = :r"),
            {"r": c.rut},
        ).scalar_one()
        assert usado is not None


class TestLasTresNegaciones:
    """**Los escenarios que de verdad hay que proteger.**

    Emitir se ve funcionando; negar, no. Un fallo aca deja entrar a quien no
    corresponde y nada en la pantalla lo delata.
    """

    def test_credenciales_inventadas(self, db: Session) -> None:
        """Escenario: alguien prueba un RUT y una clave que nunca se emitieron."""
        assert autenticar(db, EMPRESA_A, "90123456-7", "ABC234") is None

    def test_clave_incorrecta_sobre_un_rut_que_si_existe(self, db: Session) -> None:
        c = emitir(db, EMPRESA_A)
        db.flush()

        assert autenticar(db, EMPRESA_A, c.rut, "XXXXXX") is None

    def test_credenciales_vencidas(self, db: Session) -> None:
        """Escenario: la credencial caduco."""
        c = emitir(db, EMPRESA_A)
        db.flush()
        # **Se mueven las dos fechas, no solo una.** El CHECK
        # `ck_guest_credentials_vigencia` exige `valid_until > created_at`, asi
        # que envejecer solo el vencimiento produce un dato imposible y la
        # prueba falla por la restriccion en vez de por lo que quiere medir.
        db.execute(
            text(
                "UPDATE guest_credentials "
                "SET created_at = now() - interval '40 days', "
                "    valid_until = now() - interval '1 day' "
                "WHERE rut = :r"
            ),
            {"r": c.rut},
        )

        assert autenticar(db, EMPRESA_A, c.rut, c.clave) is None

    def test_una_credencial_revocada_no_sirve(self, db: Session) -> None:
        """Se revoca sin borrar: si se filtro, hay que poder cortarla **y**
        conservar el rastro de que solicitudes abrio."""
        c = emitir(db, EMPRESA_A)
        db.flush()
        db.execute(
            text("UPDATE guest_credentials SET revoked_at = now() WHERE rut = :r"),
            {"r": c.rut},
        )

        assert autenticar(db, EMPRESA_A, c.rut, c.clave) is None

    def test_un_rut_mal_formado_no_llega_a_consultar(self, db: Session) -> None:
        for malo in ["", "no-es-un-rut", "12345678-X", None]:
            assert autenticar(db, EMPRESA_A, malo, "ABC234") is None

    def test_sin_clave_no_entra(self, db: Session) -> None:
        """Comprueba **el resultado, no la guarda temprana**.

        `autenticar()` corta antes de consultar cuando la clave viene vacia,
        pero quitar esa guarda no cambia nada: la cadena vacia tampoco calza
        con el hash. La guarda ahorra una consulta; lo que protege el acceso es
        la comparacion. Se deja dicho para que nadie lea esta prueba como que
        cubre esa linea.
        """
        c = emitir(db, EMPRESA_A)
        db.flush()

        assert autenticar(db, EMPRESA_A, c.rut, "") is None


class TestUnInvitadoNoCruzaDeEmpresa:
    """Escenario: credenciales de la empresa A contra la empresa B.

    **Es la negacion mas peligrosa de las tres.** Las otras dos le niegan el
    acceso a quien no lo tiene; esta impide que quien si lo tiene vea los datos
    de otro cliente.
    """

    def test_la_credencial_de_una_empresa_no_sirve_en_la_otra(
        self, engine
    ) -> None:
        """**Dos barreras independientes sostienen esto**, y se comprobo.

        Quitar el `tenant_id = :t` de la consulta no rompe esta prueba: RLS ya
        oculta las filas de la otra empresa. Y apagar RLS tampoco la rompe: el
        filtro de la consulta la sostiene. Lo que cae al apagar RLS es la
        prueba de abajo, que consulta sin filtro a proposito — por eso las dos
        tienen que existir.
        """
        sesion_a = _sesion(engine, EMPRESA_A)
        try:
            c = emitir(sesion_a, EMPRESA_A)
            sesion_a.commit()
        except Exception:
            sesion_a.rollback()
            sesion_a.info["_conexion"].close()
            raise

        sesion_b = _sesion(engine, EMPRESA_B)
        try:
            # Misma credencial, empresa equivocada.
            assert autenticar(sesion_b, EMPRESA_B, c.rut, c.clave) is None
        finally:
            sesion_b.rollback()
            sesion_b.info["_conexion"].close()
            sesion_b.close()

            # Se limpia lo que se confirmo: esta prueba escribe de verdad
            # porque necesita que la fila exista para la otra sesion.
            limpieza = _sesion(engine, EMPRESA_A)
            limpieza.execute(
                text("DELETE FROM guest_credentials WHERE rut = :r"), {"r": c.rut}
            )
            limpieza.commit()
            limpieza.info["_conexion"].close()
            limpieza.close()
            sesion_a.info["_conexion"].close()
            sesion_a.close()

    def test_rls_no_muestra_las_credenciales_de_otra_empresa(
        self, engine
    ) -> None:
        """**La barrera de verdad, comprobada.**

        La tabla nacio en una migracion, y el bucle de politicas de `01_schema`
        corre una sola vez: sin declarar su propia politica, la tabla habria
        quedado visible entre empresas sin que nada fallara.
        """
        sesion_a = _sesion(engine, EMPRESA_A)
        try:
            c = emitir(sesion_a, EMPRESA_A)
            sesion_a.commit()
        except Exception:
            sesion_a.rollback()
            sesion_a.info["_conexion"].close()
            raise

        sesion_b = _sesion(engine, EMPRESA_B)
        try:
            visible = sesion_b.execute(
                text("SELECT count(*) FROM guest_credentials WHERE rut = :r"),
                {"r": c.rut},
            ).scalar_one()
            assert visible == 0, "RLS no esta aislando `guest_credentials`"
        finally:
            sesion_b.rollback()
            sesion_b.info["_conexion"].close()
            sesion_b.close()

            limpieza = _sesion(engine, EMPRESA_A)
            limpieza.execute(
                text("DELETE FROM guest_credentials WHERE rut = :r"), {"r": c.rut}
            )
            limpieza.commit()
            limpieza.info["_conexion"].close()
            limpieza.close()
            sesion_a.info["_conexion"].close()
            sesion_a.close()


class TestLoQueNoAbreLaCredencial:
    """El invitado **no alcanza los datos de negocio** (escenario 5).

    Se comprueba por el tipo: `autenticar()` devuelve `InvitadoAutenticado`, que
    no es `CurrentUser`. Ningun endpoint de negocio puede aceptarlo por
    accidente porque ni siquiera sabe leerlo — la incompatibilidad la verifica
    el verificador de tipos, no la memoria de quien escribe el endpoint.
    """

    def test_no_devuelve_un_current_user(self, db: Session) -> None:
        from app.auth import CurrentUser

        c = emitir(db, EMPRESA_A)
        db.flush()

        quien = autenticar(db, EMPRESA_A, c.rut, c.clave)

        assert quien is not None
        assert not isinstance(quien, CurrentUser)
        # Y no trae `user_id`: no hay usuario que suplantar.
        assert not hasattr(quien, "user_id")
