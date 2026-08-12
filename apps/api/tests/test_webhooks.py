"""Webhook de Clerk: verificacion de firma y sincronizacion de usuarios.

Las firmas se generan de verdad con `svix`, no se simulan: asi el test ejercita
el mismo camino que un evento real de Clerk, incluida la parte que rechaza lo
que viene mal firmado.

La base se reemplaza por un doble en memoria. Lo que se prueba aca es la
traduccion de eventos a filas, no el motor SQL.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from svix.webhooks import Webhook

from app.config import get_settings
from app.main import app
from app.deps import get_admin_db
from app.services import clerk_sync
from app.services.clerk_sync import DatosDeClerkInvalidos, procesar_evento

TENANT = str(uuid4())
SECRETO = "whsec_" + base64.b64encode(b"secreto-de-prueba-para-webhooks").decode()


# --- Doble de sesion ---------------------------------------------------------


class UsuarioFalso:
    """Solo los campos que el sincronizador toca."""

    def __init__(self, **kw):
        self.clerk_id = kw.get("clerk_id")
        self.email = kw.get("email")
        self.full_name = kw.get("full_name")
        self.tenant_id = kw.get("tenant_id")
        self.user_type = kw.get("user_type")
        self.status = kw.get("status")


class SesionFalsa:
    def __init__(self, usuarios=None):
        self.usuarios: list = list(usuarios or [])
        self.agregados: list = []
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, stmt):
        """Resuelve el WHERE leyendo el valor literal del binario del criterio.

        Es fragil por naturaleza, pero alcanza porque el servicio solo hace dos
        busquedas: por `clerk_id` y por `email`.
        """
        criterio = stmt.whereclause
        columna = criterio.left.name
        valor = criterio.right.value
        for u in self.usuarios:
            if getattr(u, columna, None) == valor:
                return u
        return None

    def add(self, obj):
        self.agregados.append(obj)
        self.usuarios.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


# --- Datos de ejemplo --------------------------------------------------------


def evento_usuario(**over) -> dict:
    data = {
        "id": "user_2abcdef",
        "email_addresses": [
            {"id": "idn_1", "email_address": "ana.rojas@ecogestion.cl"},
        ],
        "primary_email_address_id": "idn_1",
        "first_name": "Ana",
        "last_name": "Rojas",
        "public_metadata": {"tenant_id": TENANT, "role": "tenant_admin"},
    }
    data.update(over)
    return data


@pytest.fixture
def cliente(monkeypatch):
    """TestClient con el secreto configurado y la base reemplazada."""
    monkeypatch.setenv("CLERK_WEBHOOK_SECRET", SECRETO)
    get_settings.cache_clear()

    sesion = SesionFalsa()
    app.dependency_overrides[get_admin_db] = lambda: sesion
    with TestClient(app) as c:
        c.sesion = sesion  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def firmar(cuerpo: bytes, secreto: str = SECRETO) -> dict[str, str]:
    """Las tres cabeceras del protocolo svix, firmadas de verdad."""
    ahora = datetime.now(timezone.utc)
    firma = Webhook(secreto).sign("msg_test", ahora, cuerpo.decode())
    return {
        "svix-id": "msg_test",
        "svix-timestamp": str(int(ahora.timestamp())),
        "svix-signature": firma,
        "content-type": "application/json",
    }


def enviar(cliente, tipo: str, data: dict, *, secreto: str = SECRETO):
    cuerpo = json.dumps({"type": tipo, "data": data}).encode()
    return cliente.post(
        "/api/v1/webhooks/clerk",
        content=cuerpo,
        headers=firmar(cuerpo, secreto),
    )


# --- Verificacion de firma ---------------------------------------------------


def test_firma_valida_crea_el_usuario(cliente):
    r = enviar(cliente, "user.created", evento_usuario())

    assert r.status_code == 200
    assert r.json()["result"] == "creado"
    creado = cliente.sesion.agregados[0]
    assert creado.clerk_id == "user_2abcdef"
    assert creado.email == "ana.rojas@ecogestion.cl"
    assert creado.full_name == "Ana Rojas"
    assert creado.user_type == "tenant_admin"
    assert creado.status == "active"


def test_firma_de_otro_secreto_da_400(cliente):
    otro = "whsec_" + base64.b64encode(b"un-secreto-que-no-es-el-nuestro").decode()

    r = enviar(cliente, "user.created", evento_usuario(), secreto=otro)

    assert r.status_code == 400
    assert cliente.sesion.agregados == []


def test_sin_cabeceras_de_firma_da_400(cliente):
    r = cliente.post(
        "/api/v1/webhooks/clerk",
        content=json.dumps({"type": "user.created", "data": evento_usuario()}),
        headers={"content-type": "application/json"},
    )

    assert r.status_code == 400


def test_cuerpo_alterado_despues_de_firmar_da_400(cliente):
    """Lo que la firma protege: que nadie cambie el tenant en el camino."""
    original = json.dumps({"type": "user.created", "data": evento_usuario()}).encode()
    cabeceras = firmar(original)
    alterado = original.replace(TENANT.encode(), str(uuid4()).encode())

    r = cliente.post("/api/v1/webhooks/clerk", content=alterado, headers=cabeceras)

    assert r.status_code == 400


def test_sin_secreto_configurado_da_503(monkeypatch):
    """503 y no 401: el que llama no tiene la culpa de que falte la config."""
    monkeypatch.delenv("CLERK_WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()
    sesion = SesionFalsa()
    app.dependency_overrides[get_admin_db] = lambda: sesion

    with TestClient(app) as c:
        r = c.post(
            "/api/v1/webhooks/clerk",
            content=json.dumps({"type": "user.created", "data": {}}),
            headers={"content-type": "application/json"},
        )

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    assert r.status_code == 503


# --- Eventos -----------------------------------------------------------------


def test_un_evento_desconocido_responde_200_y_no_toca_nada(cliente):
    """200 para que Clerk no lo reintente para siempre."""
    r = enviar(cliente, "session.created", {"id": "sess_1"})

    assert r.status_code == 200
    assert r.json()["result"] == "ignorado"
    assert cliente.sesion.agregados == []


def test_sin_tenant_id_da_400_y_no_deja_la_fila_a_medias(cliente):
    """Pasa cuando falta configurar publicMetadata en el dashboard de Clerk."""
    sin_tenant = evento_usuario(public_metadata={})

    r = enviar(cliente, "user.created", sin_tenant)

    assert r.status_code == 400
    assert "tenant_id" in r.json()["detail"]
    assert cliente.sesion.rollbacks == 1
    assert cliente.sesion.commits == 0


# --- Traduccion de eventos (sin HTTP) ---------------------------------------


def test_se_adopta_un_usuario_que_ya_existia_por_su_correo():
    """Lo que evita duplicar a alguien que estaba antes de que hubiera Clerk."""
    previo = UsuarioFalso(
        clerk_id=None,
        email="ana.rojas@ecogestion.cl",
        full_name="Ana Rojas",
        tenant_id=TENANT,
        user_type="tenant_admin",
        status="invited",
    )
    db = SesionFalsa([previo])

    resultado = procesar_evento(db, "user.created", evento_usuario())

    assert resultado == "actualizado"
    assert db.agregados == [], "no debe crear una fila nueva"
    assert previo.clerk_id == "user_2abcdef"
    assert previo.status == "active", "la invitacion se consume al primer ingreso"


def test_no_pisa_el_tenant_ni_el_rol_en_una_actualizacion():
    """Un cambio de foto en Clerk no debe revertir lo que un admin configuro aca."""
    otro_tenant = str(uuid4())
    previo = UsuarioFalso(
        clerk_id="user_2abcdef",
        email="ana.rojas@ecogestion.cl",
        full_name="Ana",
        tenant_id=otro_tenant,
        user_type="manager",
        status="active",
    )
    db = SesionFalsa([previo])

    procesar_evento(db, "user.updated", evento_usuario(first_name="Ana Maria"))

    assert previo.full_name == "Ana Maria Rojas"
    assert previo.tenant_id == otro_tenant
    assert previo.user_type == "manager"


def test_borrar_en_clerk_deshabilita_pero_no_borra():
    """`audit_log` referencia al usuario: borrarlo dejaria huerfano el historial."""
    previo = UsuarioFalso(clerk_id="user_2abcdef", email="a@b.cl", status="active")
    db = SesionFalsa([previo])

    resultado = procesar_evento(db, "user.deleted", {"id": "user_2abcdef"})

    assert resultado == "deshabilitado"
    assert previo.status == "disabled"
    assert previo in db.usuarios, "la fila sigue existiendo"


def test_borrar_a_alguien_que_no_esta_no_falla():
    db = SesionFalsa()

    assert procesar_evento(db, "user.deleted", {"id": "user_desconocido"}) == "sin_efecto"


def test_toma_el_correo_marcado_como_primario_y_no_el_primero():
    """Con dos correos, el orden del arreglo no dice cual usa la persona."""
    data = evento_usuario(
        email_addresses=[
            {"id": "idn_1", "email_address": "viejo@personal.cl"},
            {"id": "idn_2", "email_address": "ana@empresa.cl"},
        ],
        primary_email_address_id="idn_2",
    )
    db = SesionFalsa()

    procesar_evento(db, "user.created", data)

    assert db.agregados[0].email == "ana@empresa.cl"


def test_un_usuario_sin_nombre_usa_su_correo():
    """Entrar por SSO sin perfil deja el nombre vacio, y la columna es NOT NULL."""
    db = SesionFalsa()

    procesar_evento(db, "user.created", evento_usuario(first_name=None, last_name=None))

    assert db.agregados[0].full_name == "ana.rojas@ecogestion.cl"


def test_un_rol_inventado_en_clerk_no_entra_a_la_base():
    """El CHECK de `user_type` lo rechazaria; mejor no llegar hasta ahi."""
    db = SesionFalsa()

    procesar_evento(
        db, "user.created", evento_usuario(public_metadata={"tenant_id": TENANT, "role": "dios"})
    )

    assert db.agregados[0].user_type == clerk_sync.TIPO_POR_DEFECTO


def test_un_usuario_sin_correo_es_rechazado():
    db = SesionFalsa()

    with pytest.raises(DatosDeClerkInvalidos):
        procesar_evento(db, "user.created", evento_usuario(email_addresses=[]))


def test_un_tenant_id_que_no_es_uuid_es_rechazado():
    db = SesionFalsa()

    with pytest.raises(DatosDeClerkInvalidos):
        procesar_evento(
            db, "user.created", evento_usuario(public_metadata={"tenant_id": "no-soy-uuid"})
        )
