"""El acceso del invitado por HTTP, de punta a punta (RF-01, RF-02, RF-07).

`test_invitado.py` prueba el servicio; esto prueba **lo que queda expuesto**, que
no es lo mismo. Un servicio impecable detras de un endpoint que no comprueba la
empresa del token sigue siendo una fuga, y eso solo se ve atravesando HTTP.

Las negaciones son la mitad que importa: token inventado, token de otra empresa,
credencial revocada despues de emitido el token, y solicitudes ajenas.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
ADMIN_URL = os.getenv(
    "DATABASE_ADMIN_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
)
SECRETO = "secreto-solo-de-pruebas-no-sirve-en-ningun-otro-lado"


@pytest.fixture(autouse=True)
def _sin_tope_previo():
    """Devuelve el contador a cero antes de cada prueba.

    El tope vive en el proceso y lo comparten todas: sin esto, la undecima
    prueba que pide credenciales recibe 429 y falla por una razon que no tiene
    nada que ver con lo que mide. Paso exactamente eso al escribirlas.

    **No debilita las pruebas del tope**: esas agotan el cupo dentro de una sola
    prueba y comprueban el corte ahi.
    """
    from app.limite_de_peticiones import TOPE_DE_CREDENCIALES, TOPE_DE_INGRESO

    TOPE_DE_CREDENCIALES.reiniciar()
    TOPE_DE_INGRESO.reiniciar()


@pytest.fixture
def cliente(monkeypatch):
    """La API con el secreto de firma puesto y la base local."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import SessionLocal
    from app.main import app

    ajustes = get_settings()
    monkeypatch.setattr(ajustes, "clerk_jwks_url", "", raising=False)
    monkeypatch.setattr(ajustes, "token_invitado_secreto", SECRETO, raising=False)

    original = SessionLocal.kw.get("bind")
    motor = create_engine(URL)
    try:
        motor.connect().close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    SessionLocal.configure(bind=motor)
    try:
        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original)
        motor.dispose()


@pytest.fixture
def limpiar():
    """Quita las credenciales y su rastro. Como dueno: `audit_log` es inmutable."""
    ruts: list[str] = []
    yield ruts

    admin = create_engine(ADMIN_URL)
    try:
        with admin.begin() as c:
            for rut in ruts:
                ids = [
                    f[0]
                    for f in c.execute(
                        text("SELECT id FROM guest_credentials WHERE rut = :r"),
                        {"r": rut},
                    ).all()
                ]
                for cid in ids:
                    c.execute(
                        text(
                            "DELETE FROM support_tickets WHERE guest_credential_id = :c"
                        ),
                        {"c": cid},
                    )
                    c.execute(
                        text("DELETE FROM audit_log WHERE entity_id = :c"), {"c": cid}
                    )
                c.execute(
                    text("DELETE FROM guest_credentials WHERE rut = :r"), {"r": rut}
                )
    finally:
        admin.dispose()


def _generar(cliente, empresa: str = EMPRESA_A) -> dict:
    r = cliente.post(f"/api/v1/acceso-invitado/{empresa}/credenciales")
    assert r.status_code == 201, r.text
    return r.json()


def _entrar(cliente, cred: dict, empresa: str = EMPRESA_A):
    return cliente.post(
        f"/api/v1/acceso-invitado/{empresa}/sesion",
        json={"rut": cred["rut"], "clave": cred["clave"]},
    )


class TestGenerarSinCuenta:
    """RF-02: una persona sin cuenta abre el link y recibe su acceso."""

    def test_el_link_publico_no_pide_token(self, cliente, limpiar) -> None:
        """**Sin cabecera de autenticacion ninguna.** Es la funcionalidad.

        Si esto empezara a pedir token, el Cliente Invitado dejaria de existir:
        no tiene cuenta con la cual conseguir uno.
        """
        cred = _generar(cliente)
        limpiar.append(cred["rut"])

        assert cred["clave"]
        assert cred["dias_de_vigencia"] == 30

    def test_una_empresa_que_no_existe_da_404(self, cliente) -> None:
        r = cliente.post(f"/api/v1/acceso-invitado/{uuid.uuid4()}/credenciales")
        assert r.status_code == 404

    def test_la_generacion_queda_en_el_registro(self, cliente, limpiar) -> None:
        """**El observador automatico no ve este router**, asi que si esto pasa
        es porque el endpoint lo anota a mano — que es justo lo que se puede
        olvidar al agregar un endpoint aca."""
        cred = _generar(cliente)
        limpiar.append(cred["rut"])

        motor = create_engine(URL)
        with motor.connect() as c:
            c.execute(text("SET LOCAL ROLE ambienta_app"))
            c.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": EMPRESA_A},
            )
            n = c.execute(
                text(
                    "SELECT count(*) FROM audit_log "
                    "WHERE entity_type = 'guest_credentials' AND action = 'create' "
                    "AND metadata->>'rut' = :r"
                ),
                {"r": cred["rut"]},
            ).scalar_one()
        motor.dispose()
        assert n == 1


class TestEntrar:
    """RF-01: volver con las credenciales de una visita anterior."""

    def test_las_credenciales_recien_emitidas_dan_una_sesion(
        self, cliente, limpiar
    ) -> None:
        cred = _generar(cliente)
        limpiar.append(cred["rut"])

        r = _entrar(cliente, cred)

        assert r.status_code == 200, r.text
        assert r.json()["token"]
        assert r.json()["rut"] == cred["rut"]

    def test_sin_secreto_de_firma_se_niega_en_vez_de_improvisar_uno(
        self, cliente, limpiar, monkeypatch
    ) -> None:
        """**503, no una llave por defecto.**

        Un secreto por defecto en el codigo es un secreto publicado: cualquiera
        que lea el repositorio podria firmarse una sesion de invitado de la
        empresa que quisiera. Preferible que el entorno mal configurado no
        funcione a que funcione sin proteger nada.
        """
        cred = _generar(cliente)
        limpiar.append(cred["rut"])

        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "token_invitado_secreto", "", raising=False)

        assert _entrar(cliente, cred).status_code == 503


class TestLasNegaciones:
    """**La mitad que importa.** Emitir se ve funcionando; negar, no."""

    def test_clave_incorrecta(self, cliente, limpiar) -> None:
        cred = _generar(cliente)
        limpiar.append(cred["rut"])

        r = cliente.post(
            f"/api/v1/acceso-invitado/{EMPRESA_A}/sesion",
            json={"rut": cred["rut"], "clave": "XXXXXX"},
        )
        assert r.status_code == 401

    def test_credenciales_de_una_empresa_no_sirven_en_la_otra(
        self, cliente, limpiar
    ) -> None:
        """El escenario mas peligroso del requisito."""
        cred = _generar(cliente, EMPRESA_A)
        limpiar.append(cred["rut"])

        r = _entrar(cliente, cred, EMPRESA_B)

        assert r.status_code == 401

    def test_un_token_inventado_no_abre_las_solicitudes(self, cliente) -> None:
        r = cliente.get(
            f"/api/v1/acceso-invitado/{EMPRESA_A}/mis-solicitudes",
            headers={"Authorization": "Bearer no.es.un.token"},
        )
        assert r.status_code == 401

    def test_sin_token_tampoco(self, cliente) -> None:
        r = cliente.get(f"/api/v1/acceso-invitado/{EMPRESA_A}/mis-solicitudes")
        assert r.status_code == 401

    def test_un_token_valido_de_otra_empresa_no_sirve(
        self, cliente, limpiar
    ) -> None:
        """**Token legitimo, empresa equivocada.**

        Es el fallo que un endpoint mal escrito comete sin darse cuenta: valida
        la firma, no compara la empresa, y consulta con el tenant de la URL.
        """
        cred = _generar(cliente, EMPRESA_A)
        limpiar.append(cred["rut"])
        token = _entrar(cliente, cred, EMPRESA_A).json()["token"]

        r = cliente.get(
            f"/api/v1/acceso-invitado/{EMPRESA_B}/mis-solicitudes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401

    def test_revocar_la_credencial_corta_el_token_ya_emitido(
        self, cliente, limpiar
    ) -> None:
        """**Sin esto, revocar no revocaria nada durante 30 dias.**

        El token sigue firmado y sin vencer: lo unico que lo invalida es que el
        endpoint vuelva a mirar la credencial en cada peticion.
        """
        cred = _generar(cliente)
        limpiar.append(cred["rut"])
        token = _entrar(cliente, cred).json()["token"]
        cabeceras = {"Authorization": f"Bearer {token}"}

        assert (
            cliente.get(
                f"/api/v1/acceso-invitado/{EMPRESA_A}/mis-solicitudes",
                headers=cabeceras,
            ).status_code
            == 200
        )

        motor = create_engine(URL)
        with motor.begin() as c:
            c.execute(text("SET LOCAL ROLE ambienta_app"))
            c.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": EMPRESA_A},
            )
            c.execute(
                text(
                    "UPDATE guest_credentials SET revoked_at = now() WHERE rut = :r"
                ),
                {"r": cred["rut"]},
            )
        motor.dispose()

        assert (
            cliente.get(
                f"/api/v1/acceso-invitado/{EMPRESA_A}/mis-solicitudes",
                headers=cabeceras,
            ).status_code
            == 401
        )


class TestVeSoloLoSuyo:
    """RF-07: el invitado no ve las solicitudes de otros."""

    def test_solo_los_tickets_abiertos_con_su_credencial(
        self, cliente, limpiar
    ) -> None:
        """Dos invitados **de la misma empresa**, un ticket cada uno.

        Que RLS los separe no alcanza: los dos son de la misma empresa, asi que
        para la base son igual de visibles. Lo unico que los separa es el filtro
        por credencial.
        """
        mio = _generar(cliente)
        ajeno = _generar(cliente)
        limpiar.extend([mio["rut"], ajeno["rut"]])

        motor = create_engine(URL)
        with motor.begin() as c:
            c.execute(text("SET LOCAL ROLE ambienta_app"))
            c.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": EMPRESA_A},
            )
            for rut, asunto in ((mio["rut"], "Lo mio"), (ajeno["rut"], "Lo ajeno")):
                cid = c.execute(
                    text("SELECT id FROM guest_credentials WHERE rut = :r"),
                    {"r": rut},
                ).scalar_one()
                c.execute(
                    text(
                        "INSERT INTO support_tickets "
                        "(tenant_id, ticket_number, guest_name, guest_email, "
                        " category, subject, description, guest_credential_id) "
                        "VALUES (:t, :n, 'Invitado', :e, 'other', :s, 'x', :c)"
                    ),
                    {
                        "t": EMPRESA_A,
                        "n": f"T-{uuid.uuid4().hex[:10]}",
                        "e": f"{rut}@ejemplo.cl",
                        "s": asunto,
                        "c": cid,
                    },
                )
        motor.dispose()

        token = _entrar(cliente, mio).json()["token"]
        r = cliente.get(
            f"/api/v1/acceso-invitado/{EMPRESA_A}/mis-solicitudes",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert r.status_code == 200, r.text
        asuntos = [s["subject"] for s in r.json()]
        assert asuntos == ["Lo mio"], f"Vio algo que no es suyo: {asuntos}"


class TestLoQueElTokenTieneQueDecir:
    """Tres propiedades del token que **ninguna prueba cubria**.

    Aparecieron rompiendo el codigo a proposito: quitar la validacion de
    caducidad, la de emisor y la de tipo no hacia fallar nada.

    **La primera version de estas pruebas era vacua** y paso en verde igual. El
    token forjado llevaba un `sub` inventado, asi que moria en la comprobacion
    de credencial y nunca llegaba a validarse el `exp`: daban 401 por el motivo
    equivocado. Por eso ahora se forja sobre una credencial **real y vigente**,
    de modo que lo unico malo del token sea lo que la prueba dice medir.
    """

    def _credencial_real(self, cliente, limpiar) -> str:
        """Emite una credencial de verdad y devuelve su id.

        Sin esto la prueba no mide nada: hay que llegar hasta la validacion del
        token con todo lo demas en orden.
        """
        cred = _generar(cliente)
        limpiar.append(cred["rut"])
        motor = create_engine(URL)
        with motor.connect() as c:
            c.execute(text("SET LOCAL ROLE ambienta_app"))
            c.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": EMPRESA_A},
            )
            cid = c.execute(
                text("SELECT id FROM guest_credentials WHERE rut = :r"),
                {"r": cred["rut"]},
            ).scalar_one()
        motor.dispose()
        return str(cid)

    def _forjar(self, **cambios) -> str:
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        from app.services import token_invitado as ti

        payload = {
            "iss": ti.EMISOR,
            "tipo": ti.TIPO,
            "sub": str(uuid.uuid4()),
            "tenant_id": EMPRESA_A,
            "rut": "90000000-7",
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
            "iat": datetime.now(timezone.utc),
        }
        payload.update(cambios)
        return jwt.encode(payload, SECRETO, algorithm=ti.ALGORITMO)

    def _pedir(self, cliente, token: str) -> int:
        return cliente.get(
            f"/api/v1/acceso-invitado/{EMPRESA_A}/mis-solicitudes",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code

    def test_un_token_vencido_no_sirve(self, cliente, limpiar) -> None:
        """**La vigencia de 30 dias es la promesa entera del diseno.**

        Sin esta comprobacion, una credencial entregada a un desconocido —que es
        como se entregan todas— no caduca nunca.
        """
        from datetime import datetime, timedelta, timezone

        vencido = self._forjar(
            sub=self._credencial_real(cliente, limpiar),
            exp=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        assert self._pedir(cliente, vencido) == 401

    def test_un_token_de_otro_emisor_no_sirve(self, cliente, limpiar) -> None:
        """Aunque este firmado con el mismo secreto.

        Es la defensa por si el secreto se compartiera alguna vez con otro
        servicio: firmar no alcanza, hay que ser este emisor.
        """
        forjado = self._forjar(
            sub=self._credencial_real(cliente, limpiar), iss="otra-cosa"
        )
        assert self._pedir(cliente, forjado) == 401

    def test_un_token_nuestro_de_otro_proposito_no_sirve(
        self, cliente, limpiar
    ) -> None:
        """El campo `tipo` no sobra.

        Sin el, cualquier token que esta API firmara en el futuro con el mismo
        secreto —un enlace de descarga, un correo de confirmacion— valdria como
        sesion de invitado.
        """
        forjado = self._forjar(
            sub=self._credencial_real(cliente, limpiar), tipo="descarga"
        )
        assert self._pedir(cliente, forjado) == 401


class TestAbrirUnaSolicitud:
    """RF-02: el invitado abre su solicitud, **ligada a su credencial**.

    Ese vinculo es la mitad que no se ve: sin el, el ticket queda a nombre de un
    correo escrito a mano y no hay forma de comprobar despues que es de quien
    dice ser — o sea que nadie puede recuperarlo, que es justo lo que RF-07
    pide poder hacer.
    """

    def _abrir(self, cliente, token: str, **campos):
        cuerpo = {"subject": "Se me vencio un permiso", "description": "Detalle."}
        cuerpo.update(campos)
        return cliente.post(
            f"/api/v1/acceso-invitado/{EMPRESA_A}/solicitudes",
            headers={"Authorization": f"Bearer {token}"},
            json=cuerpo,
        )

    def test_la_solicitud_queda_ligada_a_la_credencial(
        self, cliente, limpiar
    ) -> None:
        cred = _generar(cliente)
        limpiar.append(cred["rut"])
        token = _entrar(cliente, cred).json()["token"]

        r = self._abrir(cliente, token)

        assert r.status_code == 201, r.text
        # Y aparece de inmediato en lo suyo, que es la prueba de que el vinculo
        # se escribio y no solo de que el INSERT no fallo.
        mias = cliente.get(
            f"/api/v1/acceso-invitado/{EMPRESA_A}/mis-solicitudes",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        assert [s["ticket_number"] for s in mias] == [r.json()["ticket_number"]]

    def test_el_numero_lo_pone_la_base(self, cliente, limpiar) -> None:
        """No lo calcula Python.

        La unicidad del numero es **global**, no por empresa: un `max()+1` en la
        aplicacion abre una carrera entre peticiones de empresas distintas.
        """
        cred = _generar(cliente)
        limpiar.append(cred["rut"])
        token = _entrar(cliente, cred).json()["token"]

        uno = self._abrir(cliente, token).json()["ticket_number"]
        otro = self._abrir(cliente, token).json()["ticket_number"]

        assert uno != otro
        assert uno.startswith("TKT-")

    def test_sin_token_no_se_puede_abrir(self, cliente) -> None:
        r = cliente.post(
            f"/api/v1/acceso-invitado/{EMPRESA_A}/solicitudes",
            json={"subject": "Intento", "description": "Sin credencial."},
        )
        assert r.status_code == 401

    def test_una_categoria_inventada_se_rechaza_con_mensaje(
        self, cliente, limpiar
    ) -> None:
        """422 con las opciones, no un 500 por violacion de CHECK.

        Un error de restriccion a mitad del commit se lee como un problema de la
        base y no de lo que mando quien llama.
        """
        cred = _generar(cliente)
        limpiar.append(cred["rut"])
        token = _entrar(cliente, cred).json()["token"]

        r = self._abrir(cliente, token, category="urgentisimo")

        assert r.status_code == 422
        assert "technical" in r.json()["detail"]

    def test_sin_correo_igual_se_puede_abrir(self, cliente, limpiar) -> None:
        """El CHECK de la tabla exige autor: usuario **o** correo.

        Un invitado no es usuario, asi que sin correo el INSERT violaria
        `ck_support_tickets_autor`. Se deriva uno del RUT: no sirve para
        escribirle, pero deja constancia de con que credencial se abrio.
        """
        cred = _generar(cliente)
        limpiar.append(cred["rut"])
        token = _entrar(cliente, cred).json()["token"]

        assert self._abrir(cliente, token).status_code == 201


    def test_abrir_una_solicitud_queda_en_el_registro(
        self, cliente, limpiar
    ) -> None:
        """Se anota a mano, como todo en este router.

        Apareció rompiéndolo a propósito: quitar el `_anotar()` de la apertura no
        hacía fallar nada. Es exactamente el olvido contra el que advierte el
        docstring del módulo — no deja rastro y nada avisa.
        """
        from app.limite_de_peticiones import TOPE_DE_CREDENCIALES

        TOPE_DE_CREDENCIALES.reiniciar()
        cred = _generar(cliente)
        limpiar.append(cred["rut"])
        token = _entrar(cliente, cred).json()["token"]

        numero = self._abrir(cliente, token).json()["ticket_number"]

        motor = create_engine(URL)
        with motor.connect() as c:
            c.execute(text("SET LOCAL ROLE ambienta_app"))
            c.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": EMPRESA_A},
            )
            n = c.execute(
                text(
                    "SELECT count(*) FROM audit_log WHERE metadata->>'ticket' = :n"
                ),
                {"n": numero},
            ).scalar_one()
        motor.dispose()
        assert n == 1, "Abrir una solicitud no dejó rastro"


class TestElTope:
    """El endpoint publico tiene un limite. **Y lo que ese limite no es.**"""

    def test_pedir_credenciales_sin_parar_termina_en_429(
        self, cliente, limpiar
    ) -> None:
        from app.limite_de_peticiones import TOPE_DE_CREDENCIALES

        TOPE_DE_CREDENCIALES.reiniciar()
        try:
            codigos = []
            for _ in range(TOPE_DE_CREDENCIALES.maximo + 2):
                r = cliente.post(
                    f"/api/v1/acceso-invitado/{EMPRESA_A}/credenciales"
                )
                codigos.append(r.status_code)
                if r.status_code == 201:
                    limpiar.append(r.json()["rut"])

            assert 429 in codigos, f"Nunca corto: {codigos}"
            assert codigos[0] == 201, "Corto desde la primera, que es peor que no cortar"
        finally:
            # Si no, la siguiente prueba arranca sin cupo y falla por esto.
            TOPE_DE_CREDENCIALES.reiniciar()

    def test_el_429_no_dice_cuanto_falta(self, cliente, limpiar) -> None:
        """Decir cuantas van o cuanto queda es decirle a quien prueba cada
        cuanto reintentar para no chocar."""
        from app.limite_de_peticiones import TOPE_DE_CREDENCIALES

        TOPE_DE_CREDENCIALES.reiniciar()
        try:
            for _ in range(TOPE_DE_CREDENCIALES.maximo):
                r = cliente.post(f"/api/v1/acceso-invitado/{EMPRESA_A}/credenciales")
                if r.status_code == 201:
                    limpiar.append(r.json()["rut"])

            corte = cliente.post(f"/api/v1/acceso-invitado/{EMPRESA_A}/credenciales")
            assert corte.status_code == 429
            detalle = corte.json()["detail"]
            assert not any(c.isdigit() for c in detalle), detalle
        finally:
            TOPE_DE_CREDENCIALES.reiniciar()

class TestElTopeAlEntrar:
    """**El tope que más importa de los dos.**

    Generar credenciales sin parar ensucia la tabla. Probar claves sin parar es
    otra cosa: son 6 caracteres de un alfabeto de 32, y sin límite un script las
    recorre. Con límite deja de ser un camino.
    """

    def test_probar_claves_sin_parar_termina_en_429(self, cliente, limpiar) -> None:
        from app.limite_de_peticiones import TOPE_DE_CREDENCIALES, TOPE_DE_INGRESO

        TOPE_DE_CREDENCIALES.reiniciar()
        TOPE_DE_INGRESO.reiniciar()
        try:
            cred = _generar(cliente)
            limpiar.append(cred["rut"])

            codigos = []
            for _ in range(TOPE_DE_INGRESO.maximo + 2):
                codigos.append(
                    cliente.post(
                        f"/api/v1/acceso-invitado/{EMPRESA_A}/sesion",
                        json={"rut": cred["rut"], "clave": "ZZZZZZ"},
                    ).status_code
                )

            assert codigos[0] == 401, "La primera debe poder equivocarse"
            assert 429 in codigos, f"Nunca cortó: {codigos}"
        finally:
            TOPE_DE_INGRESO.reiniciar()
            TOPE_DE_CREDENCIALES.reiniciar()
