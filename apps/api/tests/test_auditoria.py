"""El registro de actividades: que se anota y que no (RF-32, RNF-25).

Lo que hay que proteger no es que escriba —eso es lo facil— sino **las dos
reglas que hacen que el registro sirva**:

- Una accion que no cambio nada **no se registra**. Sin esa regla la tabla se
  llena de "actualizo la empresa" de gente que abrio un formulario y guardo sin
  tocar nada, y el ruido es lo que hace que despues nadie encuentre el cambio
  que importa. Es ademas lo que degrada la base que se quiere rotar.
- **Los secretos nunca entran.** El registro se exporta a JSON y se comparte con
  el cliente en una auditoria: un hash de contrasena ahi deja de estar
  protegido.
"""
from __future__ import annotations

import os
import re
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.auditoria import (
    ACCION_DESDE_EL_FRONTEND,
    ACCIONES,
    diferencia,
    registrar,
)

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
TENANT = uuid.UUID("a0000000-0000-0000-0000-000000000001")


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    sesion.execute(text("SET LOCAL ROLE ambienta_app"))
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(TENANT)}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


class TestLoQueNoCambioNoSeRegistra:
    def test_guardar_sin_tocar_nada_no_deja_rastro(self) -> None:
        """La regla que pidio el negocio, con esas palabras."""
        assert (
            registrar(
                db=None,  # no llega a usarse: sale antes
                tenant_id=TENANT,
                action="update",
                entity_type="tenant",
                antes={"giro": "Mineria", "direccion": "Calle 1"},
                despues={"giro": "Mineria", "direccion": "Calle 1"},
            )
            is None
        )

    def test_un_solo_campo_distinto_si_se_registra(self, db: Session) -> None:
        e = registrar(
            db,
            tenant_id=TENANT,
            action="update",
            entity_type="tenant",
            antes={"giro": "Mineria", "direccion": "Calle 1"},
            despues={"giro": "Mineria", "direccion": "Calle 2"},
        )

        assert e is not None
        # **Solo el campo que cambio.** Guardar la fila entera multiplica el
        # tamano sin agregar informacion: lo que se audita es el cambio.
        assert e.before_data == {"direccion": "Calle 1"}
        assert e.after_data == {"direccion": "Calle 2"}

    def test_una_creacion_se_registra_aunque_no_haya_antes(self, db: Session) -> None:
        """No tiene contra que comparar, y el hecho de existir ya es la informacion."""
        e = registrar(
            db,
            tenant_id=TENANT,
            action="create",
            entity_type="facility",
            despues={"name": "Planta Nueva"},
        )

        assert e is not None
        assert e.after_data == {"name": "Planta Nueva"}

    def test_una_accion_sin_datos_se_registra(self, db: Session) -> None:
        """Cerrar, aprobar, enviar: no llevan campos y ocurrieron igual."""
        e = registrar(
            db, tenant_id=TENANT, action="approve", entity_type="nonconformity"
        )

        assert e is not None
        assert e.before_data is None


class TestLosSecretosNoEntran:
    def test_una_contrasena_no_se_registra_aunque_haya_cambiado(self) -> None:
        antes, despues = diferencia(
            {"password_hash": "viejo", "email": "a@b.cl"},
            {"password_hash": "nuevo", "email": "c@d.cl"},
        )

        assert "password_hash" not in antes
        assert "password_hash" not in despues
        assert despues["email"] == "c@d.cl"

    def test_si_lo_unico_que_cambio_es_secreto_no_hay_registro(self) -> None:
        """No queda una entrada vacia diciendo que "algo" cambio.

        Seria lo peor de los dos mundos: no dice que paso y aun asi ocupa lugar.
        """
        assert (
            registrar(
                db=None,
                tenant_id=TENANT,
                action="update",
                entity_type="user",
                antes={"password_hash": "viejo"},
                despues={"password_hash": "nuevo"},
            )
            is None
        )

    @pytest.mark.parametrize(
        "campo", ["password_hash", "clerk_id", "api_key", "token", "secret_reference"]
    )
    def test_ninguno_de_los_campos_sensibles_entra(self, campo: str) -> None:
        antes, despues = diferencia({campo: "a"}, {campo: "b"})
        assert antes == {} and despues == {}


class TestLaEscrituraLlegaALaBase:
    def test_la_fila_queda_y_se_puede_leer(self, db: Session) -> None:
        eid = uuid.uuid4()
        registrar(
            db,
            tenant_id=TENANT,
            action="create",
            entity_type="obligation",
            entity_id=eid,
            despues={"titulo": "Declaracion RETC"},
        )
        db.flush()

        fila = db.execute(
            text(
                "SELECT action, entity_type, after_data FROM audit_log "
                "WHERE entity_id = :e"
            ),
            {"e": eid},
        ).first()

        assert fila is not None
        assert fila[0] == "create"
        assert fila[2] == {"titulo": "Declaracion RETC"}

    def test_la_aplicacion_no_puede_editar_lo_ya_escrito(self, db: Session) -> None:
        """RNF-25. Es la propiedad que hace que el registro valga como evidencia.

        Se comprueba de verdad y no se da por sentada: el `REVOKE` vive en un
        script de migracion, y una base recreada sin el dejaria la tabla
        editable sin que nada fallara.
        """
        eid = uuid.uuid4()
        registrar(
            db, tenant_id=TENANT, action="create", entity_type="obligation", entity_id=eid
        )
        db.flush()

        with pytest.raises(Exception) as exc:
            db.execute(
                text("UPDATE audit_log SET action = 'otra' WHERE entity_id = :e"),
                {"e": eid},
            )
        assert "permission denied" in str(exc.value).lower()


class TestElVocabularioDeAcciones:
    """Dos vocabularios distintos, no una traduccion.

    El frontend declara doce acciones y la base acepta siete, y cuatro de las
    del frontend no tienen equivalente. Enchufar uno al otro sin traducir haria
    fallar la mayoria de las escrituras contra el CHECK.
    """

    def test_un_verbo_inventado_falla_temprano_y_dice_que_hacer(self) -> None:
        with pytest.raises(ValueError) as exc:
            registrar(
                db=None, tenant_id=TENANT, action="inventado", entity_type="tenant"
            )

        # El mensaje tiene que decir cuales valen; si no, quien lo lea tiene que
        # ir a buscar el CHECK a un archivo de migracion.
        assert "create" in str(exc.value)

    def test_el_vocabulario_declarado_coincide_con_el_de_la_base(
        self, db: Session
    ) -> None:
        """Si alguien amplia el CHECK y no toca `ACCIONES`, esta prueba lo dice.

        Es la mitad que se olvida cuando el modelo esta escrito dos veces.
        """
        crudo = db.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'audit_log_action_check'"
            )
        ).scalar_one()

        en_la_base = set(re.findall(r"'([a-z_]+)'::character varying", crudo))

        assert en_la_base == set(ACCIONES)

    @pytest.mark.parametrize("del_frontend", list(ACCION_DESDE_EL_FRONTEND))
    def test_toda_accion_del_frontend_traduce_a_una_valida(
        self, del_frontend: str
    ) -> None:
        assert ACCION_DESDE_EL_FRONTEND[del_frontend] in ACCIONES
