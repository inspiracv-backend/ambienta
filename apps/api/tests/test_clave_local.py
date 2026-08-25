"""Clave local con RUT para quien entro por un proveedor externo (RF-06).

Los **seis escenarios** del requisito. Los dos que importan de verdad son los de
negacion —RUT invalido y RUT ajeno— porque fijar una clave se ve funcionando en
pantalla y rechazarla no.

## Clerk va simulado, y hay que decir que se pierde con eso

Las llamadas a la Backend API se interceptan. **No se prueba que Clerk acepte lo
que le mandamos**: si cambiara su formato de `username`, estas pruebas seguirian
en verde. Esa comprobacion es la de la Fase 5 del cambio —un script contra la
instancia real, con secretos, fuera del CI de cada PR— y existe justamente
porque los 190 tests del frontend estuvieron verdes mientras la aplicacion
estaba rota con Clerk real.

Lo que si se prueba, y no es poco: que el RUT se valide **antes** de salir a la
red, que un RUT ajeno se rechace sin decir de quien es, que el prefijo se
aplique en un solo lugar, y que nuestra fila no quede escrita si Clerk rechaza.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services import clave_local
from app.services.clave_local import (
    ClerkNoDisponible,
    ErrorDeClaveLocal,
    RutOcupado,
    fijar,
    rut_de,
    username_de,
)

TENANT = "a0000000-0000-0000-0000-000000000001"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
ADMIN_URL = os.getenv(
    "DATABASE_ADMIN_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
)

#: Un RUT valido de verdad. **Calculado, no elegido de memoria** — la primera
#: version de las tablas de RUT de este repo traia valores inventados y las
#: pruebas los delataron.
RUT_VALIDO = "12345678-5"
RUT_INVALIDO = "12345678-4"


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
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


@pytest.fixture
def con_secreto(monkeypatch):
    """Con clave secreta configurada, para no chocar con el 503 antes de tiempo."""
    from app.config import get_settings

    monkeypatch.setattr(
        get_settings(), "clerk_secret_key", "sk_test_de_mentira", raising=False
    )


@pytest.fixture
def clerk(monkeypatch):
    """Intercepta las llamadas a Clerk y anota lo que se le mando.

    Devuelve la lista de llamadas para poder afirmar sobre **lo que sale a la
    red**, no solo sobre lo que devuelve la funcion.
    """
    llamadas: list[tuple[str, str, dict]] = []

    def falso(metodo, ruta, cuerpo=None):
        llamadas.append((metodo, ruta, cuerpo or {}))
        return {"id": "user_falso", "username": (cuerpo or {}).get("username")}

    monkeypatch.setattr(clave_local, "_clerk", falso)
    return llamadas


@pytest.fixture
def usuario(db: Session):
    """Un usuario de la empresa, con su `clerk_id`. Se deshace al terminar."""
    fila = db.execute(
        text(
            "SELECT id, clerk_id, rut_tax_id FROM users "
            "WHERE tenant_id = :t AND deleted_at IS NULL LIMIT 1"
        ),
        {"t": TENANT},
    ).first()
    if fila is None:  # pragma: no cover - seed vacio
        pytest.skip("El seed no tiene usuarios en esta empresa.")
    # La transaccion de la prueba hace rollback, asi que lo que se escriba aca
    # no sobrevive. No hace falta limpiar a mano.
    return {"id": fila[0], "clerk_id": fila[1] or "user_de_prueba"}


class TestFijarLaClaveLocal:
    """Escenario 1: fijar la clave local."""

    def test_acepta_un_rut_valido_y_lo_guarda_en_users(
        self, db, usuario, clerk, con_secreto
    ) -> None:
        fijada = fijar(
            db,
            user_id=usuario["id"],
            clerk_id=usuario["clerk_id"],
            rut=RUT_VALIDO,
            clave="una-clave-larga",
        )

        assert fijada.rut == RUT_VALIDO
        guardado = db.execute(
            text("SELECT rut_tax_id FROM users WHERE id = :u"), {"u": usuario["id"]}
        ).scalar_one()
        # D5: duplicado a proposito. Es dato de negocio, no solo credencial, y
        # no se puede depender de una llamada a Clerk en cada pantalla.
        assert guardado == RUT_VALIDO

    def test_a_clerk_le_llega_el_username_con_prefijo(
        self, db, usuario, clerk, con_secreto
    ) -> None:
        """**El RUT crudo no sirve como username** y el fallo es traicionero.

        Clerk rechaza los que son solo digitos, y un RUT lo es salvo cuando el
        verificador es K: funcionaria en 1 de cada 11 casos, que es peor que no
        funcionar nunca porque parece que anda.
        """
        fijar(
            db,
            user_id=usuario["id"],
            clerk_id=usuario["clerk_id"],
            rut=RUT_VALIDO,
            clave="una-clave-larga",
        )

        metodo, ruta, cuerpo = clerk[0]
        assert metodo == "PATCH"
        assert ruta == f"/users/{usuario['clerk_id']}"
        assert cuerpo["username"] == "rut12345678-5"
        assert not cuerpo["username"].isdigit()

    def test_la_clave_va_a_clerk_y_no_a_nuestra_base(
        self, db, usuario, clerk, con_secreto
    ) -> None:
        """`users.password_hash` **no se toca**, y esa es la decision D1.

        Dos almacenes de contrasenas serian dos politicas de robustez y dos
        lugares donde revocar una sesion.

        Se compara antes contra despues y **no contra `None`**: el seed ya deja
        un hash bcrypt en esa columna. La primera version de esta prueba
        afirmaba que quedaba vacia y fallo — lo cual dejo a la vista algo que
        conviene saber: **hay hashes de contrasena sembrados que no autentican
        nada**, porque quien autentica es Clerk. Son residuo del modelo previo.
        """
        antes = db.execute(
            text("SELECT password_hash FROM users WHERE id = :u"), {"u": usuario["id"]}
        ).scalar_one()

        fijar(
            db,
            user_id=usuario["id"],
            clerk_id=usuario["clerk_id"],
            rut=RUT_VALIDO,
            clave="una-clave-larga",
        )

        assert clerk[0][2]["password"] == "una-clave-larga"
        despues = db.execute(
            text("SELECT password_hash FROM users WHERE id = :u"), {"u": usuario["id"]}
        ).scalar_one()
        assert despues == antes, "fijar() escribio en nuestro almacen de claves"


class TestElRutEnCualquierFormato:
    """Escenario 3: con puntos, sin puntos o sin guion, es el mismo RUT."""

    @pytest.mark.parametrize(
        "escrito", ["12.345.678-5", "12345678-5", "123456785", "12345678-5 "]
    )
    def test_los_formatos_dan_el_mismo_rut(
        self, db, usuario, clerk, con_secreto, escrito
    ) -> None:
        fijada = fijar(
            db,
            user_id=usuario["id"],
            clerk_id=usuario["clerk_id"],
            rut=escrito,
            clave="una-clave-larga",
        )
        assert fijada.rut == RUT_VALIDO
        assert clerk[-1][2]["username"] == "rut12345678-5"

    def test_la_traduccion_va_y_vuelve(self) -> None:
        """El prefijo se pone y se quita en **un solo lugar**.

        Si las dos puntas lo hicieran por su cuenta, se desincronizarian y el
        sintoma seria "mi RUT no me deja entrar", que se lee como culpa de quien
        escribe.
        """
        assert rut_de(username_de(RUT_VALIDO)) == RUT_VALIDO
        assert rut_de("otra-cosa") is None
        assert rut_de("") is None


class TestLasNegaciones:
    """Escenarios 4 y 5. **La mitad que no se ve funcionando.**"""

    def test_un_verificador_que_no_cierra_se_rechaza_antes_de_salir_a_la_red(
        self, db, usuario, clerk, con_secreto
    ) -> None:
        """El requisito dice *antes de enviarlo*, y por eso se comprueba que no
        hubo llamada: mandarlo seria contarle a Clerk un RUT que no existe."""
        with pytest.raises(ErrorDeClaveLocal) as exc:
            fijar(
                db,
                user_id=usuario["id"],
                clerk_id=usuario["clerk_id"],
                rut=RUT_INVALIDO,
                clave="una-clave-larga",
            )

        assert "no es valido" in str(exc.value).lower()
        assert clerk == [], "Salio a la red con un RUT invalido"

    def test_un_rut_de_otra_persona_se_rechaza_sin_decir_de_quien(
        self, db, usuario, clerk, con_secreto
    ) -> None:
        """**El escenario que convierte un formulario en un buscador de personas.**

        Si el mensaje dijera de quien es, cualquiera podria averiguar si una
        persona concreta es usuaria del sistema escribiendo su RUT.
        """
        otro = db.execute(
            text(
                "SELECT id FROM users WHERE tenant_id = :t AND id <> :u "
                "AND deleted_at IS NULL LIMIT 1"
            ),
            {"t": TENANT, "u": usuario["id"]},
        ).scalar()
        if otro is None:  # pragma: no cover - seed con un solo usuario
            pytest.skip("Hace falta un segundo usuario en el seed.")
        db.execute(
            text("UPDATE users SET rut_tax_id = :r WHERE id = :u"),
            {"r": RUT_VALIDO, "u": otro},
        )

        with pytest.raises(RutOcupado) as exc:
            fijar(
                db,
                user_id=usuario["id"],
                clerk_id=usuario["clerk_id"],
                rut=RUT_VALIDO,
                clave="una-clave-larga",
            )

        mensaje = str(exc.value)
        assert str(otro) not in mensaje
        assert "@" not in mensaje, "El mensaje filtra un correo"
        assert clerk == [], "Salio a la red con un RUT que ya era de otro"

    def test_una_clave_corta_se_rechaza_aca(
        self, db, usuario, clerk, con_secreto
    ) -> None:
        with pytest.raises(ErrorDeClaveLocal):
            fijar(
                db,
                user_id=usuario["id"],
                clerk_id=usuario["clerk_id"],
                rut=RUT_VALIDO,
                clave="corta",
            )
        assert clerk == []

    def test_si_clerk_rechaza_no_queda_el_rut_escrito(
        self, db, usuario, con_secreto, monkeypatch
    ) -> None:
        """**El orden importa y esto lo fija.**

        Escribir primero en nuestra base dejaria un `rut_tax_id` apuntando a una
        credencial que no existe: la persona creeria que puede entrar con su RUT
        y no podria.
        """
        antes = db.execute(
            text("SELECT rut_tax_id FROM users WHERE id = :u"), {"u": usuario["id"]}
        ).scalar_one()

        def revienta(metodo, ruta, cuerpo=None):
            raise ErrorDeClaveLocal("Esa contrasena aparece en filtraciones conocidas.")

        monkeypatch.setattr(clave_local, "_clerk", revienta)

        with pytest.raises(ErrorDeClaveLocal):
            fijar(
                db,
                user_id=usuario["id"],
                clerk_id=usuario["clerk_id"],
                rut=RUT_VALIDO,
                clave="una-clave-larga",
            )

        despues = db.execute(
            text("SELECT rut_tax_id FROM users WHERE id = :u"), {"u": usuario["id"]}
        ).scalar_one()
        assert despues == antes


class TestCuandoNoSePuede:
    def test_sin_clave_secreta_no_se_improvisa(self, db, usuario, monkeypatch) -> None:
        """503 **sin tocar la red**, no un intento a ciegas con un Bearer vacio.

        Comprobar solo la excepcion no bastaba: al quitar la guarda, la prueba
        seguia pasando porque Clerk devolvia 401 y eso tambien termina en
        `ClerkNoDisponible`. O sea que pasaba **por el motivo equivocado**, y de
        paso salia a internet en una prueba unitaria. Por eso se afirma que
        `urlopen` no se llamo.
        """
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "clerk_secret_key", "", raising=False)

        salio_a_la_red = []
        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda *a, **k: salio_a_la_red.append(1),
        )

        with pytest.raises(ClerkNoDisponible):
            fijar(
                db,
                user_id=usuario["id"],
                clerk_id=usuario["clerk_id"],
                rut=RUT_VALIDO,
                clave="una-clave-larga",
            )

        assert salio_a_la_red == [], "Intento llamar a Clerk sin clave secreta"

    def test_sin_cuenta_del_proveedor_no_hay_nada_que_fijar(
        self, db, usuario, clerk, con_secreto
    ) -> None:
        """Pasa en desarrollo sin Clerk, donde la sesion no identifica a nadie.

        Fijar la clave de "el usuario actual" cuando no se sabe quien es no
        tiene ningun resultado correcto posible.
        """
        with pytest.raises(ClerkNoDisponible):
            fijar(
                db,
                user_id=usuario["id"],
                clerk_id="",
                rut=RUT_VALIDO,
                clave="una-clave-larga",
            )


class TestElMensajeDeClerkLlegaEntero:
    """Clerk explica mejor que nosotros por que rechazo una clave."""

    def test_se_devuelve_su_texto_y_no_uno_generico(self, monkeypatch) -> None:
        cuerpo = json.dumps(
            {
                "errors": [
                    {
                        "message": "Password has been found in an online data breach.",
                        "long_message": (
                            "Esa contrasena aparece en una filtracion conocida. "
                            "Elige otra."
                        ),
                    }
                ]
            }
        ).encode()

        class Falso(urllib.error.HTTPError):
            def __init__(self):
                super().__init__("u", 422, "x", {}, None)

            def read(self):
                return cuerpo

        def revienta(peticion, timeout=None):
            raise Falso()

        monkeypatch.setattr(urllib.request, "urlopen", revienta)
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "clerk_secret_key", "sk_x", raising=False)

        with pytest.raises(ErrorDeClaveLocal) as exc:
            clave_local._clerk("PATCH", f"/users/{uuid.uuid4()}", {"password": "x"})

        assert "filtracion conocida" in str(exc.value)


class TestElUserAgent:
    """**La trampa que ya costo tiempo dos veces en este repo.**

    Delante de la API de Clerk hay Cloudflare, y a un cliente que no se
    identifica como navegador le responde `403 error code: 1010` — que se lee
    como "la clave secreta no sirve". Con Ley Chile fue lo mismo, ahi con un
    401. Sin esta prueba, alguien "limpia" la constante y el sintoma vuelve
    disfrazado de problema de credenciales.
    """

    def test_la_peticion_va_con_user_agent_de_navegador(self, monkeypatch) -> None:
        capturada = {}

        class Respuesta:
            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def espia(peticion, timeout=None):
            capturada["ua"] = peticion.get_header("User-agent")
            capturada["auth"] = peticion.get_header("Authorization")
            return Respuesta()

        monkeypatch.setattr(urllib.request, "urlopen", espia)
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "clerk_secret_key", "sk_x", raising=False)

        clave_local._clerk("GET", "/users")

        assert "Mozilla" in (capturada["ua"] or ""), capturada["ua"]
        assert capturada["auth"] == "Bearer sk_x"
