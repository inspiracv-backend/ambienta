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
